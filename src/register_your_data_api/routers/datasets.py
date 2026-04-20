"""Implementation for /reporting-org end points"""

import uuid

import fastapi
import starlette.requests
from fastapi import Depends, Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import Filter, SuiteCRM  # type: ignore

from register_your_data_api.dependencies import get_suitecrm_audit_headers
from register_your_data_api.exception_handlers import format_log_msg
from register_your_data_api.util import Context
from register_your_data_api.utilities import assert_precondition_met, check_crm_record_exists, get_num_crm_records

from ..auth import authz
from ..auth import models as auth_models
from ..data_handling.converters import (
    get_dataset_actions_from_suitecrm_response,
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

router = fastapi.APIRouter(prefix="/api/v1/datasets")


@router.post("", status_code=201)
def create_dataset(
    request: starlette.requests.Request,
    dataset: DatasetCreateModel,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset"]),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> DatasetSingleResponse:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    trace_id: uuid.UUID = uuid.uuid4()

    # Check the user has permission to create datasets for the specified
    # reporting org
    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
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
        user.user_id_crm,
        user.client_id,
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
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: get_num_crm_records(crm, "IATI_Datasets", {"iati_short_name": dataset.short_name}) == 0,
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

    context.audit_logger.info(
        format_log_msg(
            request,
            user.user_id_crm,
            user.client_id,
            f"trace id: {trace_id} - Created dataset with id: {suitecrm_dataset['id']}",
            include_client_id=True,
        )
    )

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

    ds_filters = Filter().equal("id", str(dataset_id))
    dataset_from_suitecrm = crm.get_records("IATI_Datasets", filters=ds_filters)

    datasets = get_dataset_list_from_suitecrm_response(dataset_from_suitecrm)

    # Check that the dataset exists and is unique
    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: len(datasets) == 1,
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        audit_log_msg=(
            f"User id {user.user_id_crm} attempted to access dataset with ID {dataset_id} which does not exist."
        ),
        public_msg=f"There is no dataset with ID {dataset_id} in the Registry.",
    )

    dataset = datasets[0]

    suitecrm_actions = crm.get_relationship("IATI_Datasets", str(dataset_id), "iati_dataset_actions")

    dataset.actions = get_dataset_actions_from_suitecrm_response(suitecrm_actions)

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

    trace_id: uuid.UUID = uuid.uuid4()

    # Fetch the original dataset record so we know which reporting org it belongs to
    ds_filters = Filter()
    ds_filters.equal("id", str(dataset_id))
    original_dataset_record_from_suitecrm = crm.get_records(
        "IATI_Datasets", fields=["iati_dataset_owner_org_id", "iati_short_name", "iati_visibility"], filters=ds_filters
    )

    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: len(original_dataset_record_from_suitecrm["data"]) != 0,
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        audit_log_msg=(
            f"user id: {user.user_id_crm} - PATCH /datasets/ID - request to update dataset id: "  # nosec B608
            f"{str(dataset_id)} but there is no dataset with that ID in the Registry"
        ),
        public_msg=(
            f"Error: cannot update dataset with {str(dataset_id)} as there is no dataset with that ID."  # nosec B608
        ),
    )

    owning_reporting_org = original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_dataset_owner_org_id"]

    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: user.validator.user_can_update_reporting_org_datasets(uuid.UUID(owning_reporting_org)),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        audit_log_msg=(
            f"user id: {user.user_id_crm} - PATCH /datasets/ID - request to update dataset id: "  # nosec B608
            f"{str(dataset_id)} belonging to reporting org id: {owning_reporting_org} by unauthorised user"
        ),
        public_msg=(
            "There is a problem with your credentials. If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
    )

    # Create the SuiteCRM-structured record to update the dataset
    dataset_for_suitecrm = get_suitecrm_dict_from_dataset(dataset)

    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: (
            user.validator.user_can_update_reporting_org_dataset_visibility(owning_reporting_org)
            or dataset.visibility is None
            or original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_visibility"] == dataset.visibility
        ),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        audit_log_msg=(
            f"user id: {user.user_id_crm} - PATCH /datasets/ID - request to update visibility for "  # nosec B608
            f"dataset id: {str(dataset_id)} belonging to reporting org id: {owning_reporting_org} by unauthorised user"
        ),
        public_msg=(
            "There is a problem with your credentials. If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
    )

    if dataset.visibility is None:
        dataset_for_suitecrm.pop("iati_visibility", None)

    # Check that the short name is unique
    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: (
            original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_short_name"] == dataset.short_name
            or (
                original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_short_name"] != dataset.short_name
                and get_num_crm_records(crm, "IATI_Datasets", {"iati_short_name": dataset.short_name}) == 0
            )
        ),
        status_code=fastapi.status.HTTP_409_CONFLICT,
        audit_log_msg=(
            f"user id: {user.user_id_crm} - PATCH /datasets/ID - request to update short_name for dataset id: "
            f"{str(dataset_id)} belonging to reporting org id: {owning_reporting_org} but there is already a dataset "
            f"with short_name '{dataset.short_name}' in the Registry"  # nosec B608
        ),
        public_msg=(
            "Error: unable to update dataset as there is already a dataset with short_name "  # nosec B608
            f"'{dataset.short_name}' in the Registry."
        ),
    )

    suitecrm_dataset = crm.update_record(
        "IATI_Datasets", str(dataset_id), dataset_for_suitecrm, headers=suitecrm_audit_headers
    )
    updated_dataset = get_dataset_meta_from_suitecrm_response(suitecrm_dataset["attributes"])

    context.audit_logger.info(
        format_log_msg(
            request,
            user.user_id_crm,
            user.client_id,
            f"trace id: {trace_id} - Created dataset with id: {suitecrm_dataset['id']}",
            include_client_id=True,
        )
    )

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

    trace_id: uuid.UUID = uuid.uuid4()

    # Fetch the original dataset record so we know which reporting org it belongs to
    ds_filters = Filter()
    ds_filters.equal("id", str(dataset_id))
    original_dataset_record_from_suitecrm = crm.get_records(
        "IATI_Datasets", fields=["iati_dataset_owner_org_id"], filters=ds_filters
    )

    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
        condition_func=lambda: len(original_dataset_record_from_suitecrm["data"]) == 1,
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        public_msg=f"There is no dataset with ID {str(dataset_id)} in the Registry.",
    )

    owning_reporting_org = original_dataset_record_from_suitecrm["data"][0]["attributes"]["iati_dataset_owner_org_id"]

    assert_precondition_met(
        user.user_id_crm,
        user.client_id,
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

        context.audit_logger.info(
            format_log_msg(
                request,
                user.user_id_crm,
                user.client_id,
                f"trace id: {trace_id} - Deleted dataset with id: {str(dataset_id)}",
                include_client_id=True,
            )
        )
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
