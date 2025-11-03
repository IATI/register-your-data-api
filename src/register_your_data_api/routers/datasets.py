"""Implementation for /reporting-org end points"""

import uuid

import fastapi
import starlette
from fastapi import Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import Filter, SuiteCRM  # type: ignore

from ..auth import authz
from ..auth import models as auth_models
from ..data_handling.converters import (
    get_dataset_list_from_suitecrm_response,
    get_dataset_meta_from_suitecrm_response,
    get_suitecrm_dict_from_dataset,
)
from ..data_handling.data_schemas import (
    DatasetCreateModel,
    DatasetReadModel,
    DatasetSingleResponse,
    DatasetUpdateModel,
)
from ..util import Context
from ..utilities import check_crm_record_exists

router = fastapi.APIRouter(prefix="/api/v1/datasets")


@router.post("/")
def create_dataset(
    request: starlette.requests.Request,
    dataset: DatasetCreateModel,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset"]),
) -> DatasetSingleResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    if not user.validator.user_can_create_reporting_org_datasets(uuid.UUID(dataset.owner_organisation_id)):
        context.audit_logger.error(
            f"Request to create dataset for reporting org id: {dataset.owner_organisation_id} "
            f"by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    # Permission to create datasets for a reporting org does not imply that the reporting org
    # for superadmins, so we still check the reporting org exists
    if not check_crm_record_exists(crm, "Accounts", str(dataset.owner_organisation_id)):
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"There is no organisation with ID {str(dataset.owner_organisation_id)} in the Registry.",
        )

    # Create the record on SuiteCRM to add the dataset
    dataset_for_suitecrm = get_suitecrm_dict_from_dataset(dataset)
    suitecrm_dataset = crm.create_record("IATI_Datasets", dataset_for_suitecrm)
    new_dataset = get_dataset_meta_from_suitecrm_response(suitecrm_dataset["attributes"])

    return DatasetSingleResponse(
        data=DatasetReadModel(
            id=suitecrm_dataset["id"], owner_organisation_id=dataset.owner_organisation_id, metadata=new_dataset
        ),
        error=None,
        status="success",
    )


@router.get("/{dataset_id}")
def get_dataset_detail(
    dataset_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset"]),
) -> DatasetSingleResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    ds_filters = Filter()
    ds_filters.equal("id", str(dataset_id))
    dataset_from_suitecrm = crm.get_records("IATI_Datasets", filters=ds_filters)

    datasets = get_dataset_list_from_suitecrm_response(dataset_from_suitecrm)

    if len(datasets) == 0:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"There is no dataset with ID {dataset_id} in the Registry.",
        )

    dataset = datasets[0]

    # using the owner_organisation_id of SuiteCRM response, verify the user has
    # access to read the datasets for that org
    if not user.validator.user_can_read_reporting_org_datasets(uuid.UUID(dataset.owner_organisation_id)):
        context.audit_logger.error(
            f"Request to read dataset details for dataset id: {dataset_id} and org id: "
            f"{dataset.owner_organisation_id} by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    return DatasetSingleResponse(data=dataset, error=None, status="success")


@router.patch("/{dataset_id}")
def update_dataset(
    dataset_id: uuid.UUID,
    request: starlette.requests.Request,
    dataset: DatasetUpdateModel,
    user: auth_models.UserAndCredentials = Security(
        authz.get_user_authnz, scopes=["ryd", "ryd:dataset", "ryd:dataset:update"]
    ),
) -> DatasetSingleResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    # Fetch the original dataset record so we know which reporting org it belongs to
    ds_filters = Filter()
    ds_filters.equal("id", str(dataset_id))
    original_dataset_record_from_suitecrm = crm.get_records(
        "IATI_Datasets", fields=["iati_dataset_owner_org_id"], filters=ds_filters
    )

    if len(original_dataset_record_from_suitecrm["data"]) == 0:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"There is no dataset with ID {str(dataset_id)} in the Registry.",
        )

    owning_reporting_org = original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_dataset_owner_org_id"]

    if not user.validator.user_can_update_reporting_org_datasets(uuid.UUID(owning_reporting_org)):
        context.audit_logger.error(
            f"Request to update dataset for reporting org id: {owning_reporting_org} "  # nosec B608
            f"by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    # Create the record on SuiteCRM to add the dataset
    dataset_for_suitecrm = get_suitecrm_dict_from_dataset(dataset)
    suitecrm_dataset = crm.update_record("IATI_Datasets", str(dataset_id), dataset_for_suitecrm)
    updated_dataset = get_dataset_meta_from_suitecrm_response(suitecrm_dataset["attributes"])

    return DatasetSingleResponse(
        data=DatasetReadModel(
            id=suitecrm_dataset["id"], owner_organisation_id=owning_reporting_org, metadata=updated_dataset
        ),
        error=None,
        status="success",
    )


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset:delete"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
