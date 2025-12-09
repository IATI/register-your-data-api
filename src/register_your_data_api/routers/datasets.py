"""Implementation for /reporting-org end points"""

import uuid

import fastapi
import starlette
from fastapi import Depends, Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import Filter, SuiteCRM  # type: ignore

from register_your_data_api.dependencies import get_suitecrm_audit_headers

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
from ..utilities import assert_precondition_met, check_crm_record_exists, get_num_crm_records

router = fastapi.APIRouter(prefix="/api/v1/datasets")


@router.post("")
def create_dataset(
    request: starlette.requests.Request,
    dataset: DatasetCreateModel,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset"]),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> DatasetSingleResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # Check the user has permission to create datasets for the specified
    # reporting org
    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_create_reporting_org_datasets(
            uuid.UUID(dataset.owner_organisation_id)
        ),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        audit_log_msg=(
            f"Request to create dataset for reporting org id: {dataset.owner_organisation_id} "
            f"by unauthorised user id: {user.user_id_crm}"
        ),
        public_msg=(
            "There is a problem with your credentials. If this persists please report this "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
    )

    # Although most permissions as assocaited with reporting orgs, this is not
    # the case for superadmins, so permission to create datasets for a reporting
    # org does not imply that the reporting org exists, so we check that here
    assert_precondition_met(
        context,
        condition_func=lambda: check_crm_record_exists(crm, "Accounts", str(dataset.owner_organisation_id)),
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        audit_log_msg=(
            f"Request to create dataset for non-existent reporting org id: {dataset.owner_organisation_id} "
            f"by user id: {user.user_id_crm}"
        ),
        public_msg=(f"There is no organisation with ID {str(dataset.owner_organisation_id)} in the Registry."),
    )

    # Check that the short name is unique
    assert_precondition_met(
        context,
        condition_func=lambda: get_num_crm_records(crm, "IATI_Datasets", "iati_short_name", dataset.short_name) == 0,
        status_code=fastapi.status.HTTP_409_CONFLICT,
        audit_log_msg=(
            f"Request to create dataset for reporting org id: {dataset.owner_organisation_id} by user id: "
            f"{user.user_id_crm} with non-unique short name: {dataset.short_name}"
        ),
        public_msg=(
            "Unable to create dataset as there is already a dataset with short_name "
            f"'{dataset.short_name}' in the Registry."
        ),
    )

    # Create the record on SuiteCRM to add the dataset
    dataset_for_suitecrm = get_suitecrm_dict_from_dataset(dataset)
    suitecrm_dataset = crm.create_record("IATI_Datasets", dataset_for_suitecrm, headers=suitecrm_audit_headers)
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

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

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
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> DatasetSingleResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # Fetch the original dataset record so we know which reporting org it belongs to
    ds_filters = Filter()
    ds_filters.equal("id", str(dataset_id))
    original_dataset_record_from_suitecrm = crm.get_records(
        "IATI_Datasets", fields=["iati_dataset_owner_org_id", "iati_visibility"], filters=ds_filters
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

    if (
        not user.validator.user_can_update_reporting_org_dataset_visibility(owning_reporting_org)
        and dataset.visibility is not None
        and original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_visibility"] != dataset.visibility
    ):
        context.audit_logger.error(
            f"Request to update dataset visibility for reporting org id: {owning_reporting_org} "  # nosec B608
            f"by user id: {user.user_id_crm} authorised to update dataset but not dataset visibility "
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    if dataset.visibility is None:
        dataset_for_suitecrm.pop("iati_visibility", None)

    suitecrm_dataset = crm.update_record(
        "IATI_Datasets", str(dataset_id), dataset_for_suitecrm, headers=suitecrm_audit_headers
    )
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
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> JSONResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # Fetch the original dataset record so we know which reporting org it belongs to
    ds_filters = Filter()
    ds_filters.equal("id", str(dataset_id))
    original_dataset_record_from_suitecrm = crm.get_records(
        "IATI_Datasets", fields=["iati_dataset_owner_org_id"], filters=ds_filters
    )

    assert_precondition_met(
        context,
        condition_func=lambda: len(original_dataset_record_from_suitecrm["data"]) == 1,
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        public_msg=f"There is no dataset with ID {str(dataset_id)} in the Registry.",
    )

    owning_reporting_org = original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_dataset_owner_org_id"]

    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_delete_reporting_org_datasets(uuid.UUID(owning_reporting_org)),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        public_msg=(
            "There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
        audit_log_msg=(
            f"Request to delete dataset for reporting org id: {owning_reporting_org} "  # nosec B608
            f"by unauthorised user id: {user.user_id_crm}"
        ),
    )

    try:
        crm.delete_record("IATI_Datasets", str(dataset_id), headers=suitecrm_audit_headers)
    except Exception:
        error_id = uuid.uuid4()
        context.app_logger.exception(
            f"Unexpected error deleting dataset id: {dataset_id} for reporting org id: {owning_reporting_org} "
            f"by user id: {user.user_id_crm}. Error trace id: {error_id}."
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"There was a problem deleting the dataset. Error id: {error_id}",
        )

    return fastapi.responses.JSONResponse({"status": "success", "data": None, "error": None})
