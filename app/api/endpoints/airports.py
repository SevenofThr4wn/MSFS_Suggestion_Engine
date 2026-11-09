from dataclasses import asdict
from typing import Annotated, Any
import math


from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_airport_catalog
from app.db.session import get_db
from app.db.repositories.aircraft_repository import (
    AircraftRepository,
)
from app.db.repositories.airport_preferences_repository import (
    AirportPreferencesRepository,
)
from app.providers.airport_catalog import AirportCatalog
from app.services.compatibility_service import (
    CompatibilityService,
)


router = APIRouter(
    prefix="/airports",
    tags=["Airport Engine"],
)


# ============================================================
# Request Schemas
# ============================================================


class CompatibilityRequest(BaseModel):
    """Parameters required to evaluate flight compatibility."""

    aircraft_id: int = Field(
        ...,
        gt=0,
        description=(
            "Unique database identifier of the aircraft "
            "used for the flight evaluation."
        ),
        examples=[1],
    )

    departure_code: str = Field(
        ...,
        min_length=3,
        max_length=8,
        description=(
            "Airport code identifying the departure airport."
        ),
        examples=["YBBN"],
    )

    arrival_code: str = Field(
        ...,
        min_length=3,
        max_length=8,
        description=(
            "Airport code identifying the destination airport."
        ),
        examples=["YSSY"],
    )

    distance_margin: float = Field(
        default=0.10,
        ge=0,
        le=1,
        description=(
            "Additional distance allowance applied during "
            "aircraft range evaluation. Expressed as a decimal "
            "fraction between 0 and 1. For example, 0.10 "
            "represents a 10% margin."
        ),
        examples=[0.10],
    )


class PreferencesRequest(BaseModel):
    """User-specific airport preferences and scenery settings."""

    has_addon_scenery: bool = Field(
        default=False,
        description=(
            "Indicates whether the user has installed "
            "third-party or enhanced scenery for the airport."
        ),
        examples=[True],
    )

    scenery_developer: str | None = Field(
        default=None,
        description=(
            "Name of the developer or publisher responsible "
            "for the installed airport scenery. May be null "
            "when no scenery developer is specified."
        ),
        examples=["iniBuilds"],
    )

    is_favourite: bool = Field(
        default=False,
        description=(
            "Indicates whether the airport is marked as "
            "a favourite by the user."
        ),
        examples=[True],
    )


# ============================================================
# Response Schemas
# ============================================================


class AirportSearchResponse(BaseModel):
    """Paginated response containing matching airports."""

    total: int = Field(
        ...,
        ge=0,
        description=(
            "Total number of airports matching the "
            "search criteria before pagination."
        ),
        examples=[150],
    )

    airports: list[dict[str, Any]] = Field(
        ...,
        description=(
            "Airport records matching the supplied filters, "
            "limited by the requested pagination parameters."
        ),
    )


class AirportPreferencesResponse(BaseModel):
    """Saved preferences associated with an airport."""

    icao_code: str = Field(
        ...,
        description=(
            "ICAO identifier of the airport associated "
            "with these preferences."
        ),
        examples=["YBBN"],
    )

    has_addon_scenery: bool = Field(
        ...,
        description=(
            "Whether enhanced or third-party scenery "
            "is installed for the airport."
        ),
        examples=[True],
    )

    scenery_developer: str | None = Field(
        ...,
        description=(
            "Developer of the installed airport scenery, "
            "if specified."
        ),
        examples=["iniBuilds"],
    )

    is_favourite: bool = Field(
        ...,
        description=(
            "Whether the airport is marked as a favourite."
        ),
        examples=[True],
    )


# ============================================================
# Airport Search
# ============================================================


@router.get(
    "",
    response_model=AirportSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Airports",
    description=(
        "Searches the airport catalog using optional search "
        "terms, country filters, and scenery preferences.\n\n"
        "The endpoint supports paginated retrieval of airport "
        "records from the Airport Catalog.\n\n"
        "**Available filters:**\n"
        "- **query:** Search text used to find airports.\n"
        "- **country:** Restricts results to a country.\n"
        "- **addon_only:** Returns only airports matching "
        "the add-on scenery filter.\n"
        "- **limit:** Maximum number of results per request.\n"
        "- **offset:** Number of matching results to skip.\n\n"
        "**Pagination:**\n\n"
        "The response includes the total number of matching "
        "airports and the current page of airport records.\n\n"
        "When no search text is supplied, the catalog "
        "is queried using an empty search term."
    ),
    response_description=(
        "Paginated airport search results, including "
        "the total number of matching airports."
    ),
    responses={
        422: {
            "description": (
                "Invalid search parameters. The limit must "
                "be between 1 and 100, and the offset "
                "must be non-negative."
            ),
        },
    },
)
def search_airports(
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
    query: Annotated[
        str,
        Query(
            description=(
                "Optional airport search text, such as "
                "an airport name, city, or code, depending "
                "on the catalog's search implementation."
            ),
            examples=["Brisbane"],
        ),
    ] = "",
    country: Annotated[
        str | None,
        Query(
            description=(
                "Optional country filter applied to "
                "airport search results."
            ),
            examples=["Australia"],
        ),
    ] = None,
    addon_only: Annotated[
        bool,
        Query(
            description=(
                "When enabled, restricts search results "
                "to airports matching the catalog's "
                "add-on scenery filter."
            ),
        ),
    ] = False,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description=(
                "Maximum number of airport records "
                "to return in a single request."
            ),
            examples=[50],
        ),
    ] = 50,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description=(
                "Number of matching airport records "
                "to skip before returning results."
            ),
            examples=[0],
        ),
    ] = 0,
):
    """
    Search the airport catalog with filtering and pagination.

    Args:
        catalog: Airport catalog dependency.
        query: Optional airport search text.
        country: Optional country filter.
        addon_only: Whether to apply the add-on scenery filter.
        limit: Maximum number of returned records.
        offset: Number of records to skip.

    Returns:
        AirportSearchResponse:
            Total matching airports and paginated records.
    """
    total, airports = catalog.search(
        query,
        country=country,
        addon_only=addon_only,
        limit=limit,
        offset=offset,
    )

    return {
        "total": total,
        "airports": [
            asdict(airport)
            for airport in airports
        ],
    }


# ============================================================
# Flight Compatibility Evaluation
# ============================================================


@router.post(
    "/compatibility",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Flight Compatibility",
    description=(
        "Evaluates the compatibility of an aircraft with "
        "a proposed flight between two airports.\n\n"
        "The Compatibility Service uses the supplied aircraft "
        "identifier, departure airport, destination airport, "
        "and distance margin to perform its evaluation.\n\n"
        "**Evaluation process:**\n"
        "1. Receives the proposed flight parameters.\n"
        "2. Retrieves aircraft information from the database.\n"
        "3. Uses the Airport Catalog to obtain airport data.\n"
        "4. Executes the Compatibility Service evaluation.\n"
        "5. Returns the calculated compatibility results.\n\n"
        "**Distance margin:**\n\n"
        "The optional distance margin provides an additional "
        "allowance when assessing aircraft range. The default "
        "is 0.10, representing a 10% allowance.\n\n"
        "**Error handling:**\n"
        "- **404:** Required aircraft or airport data "
        "could not be located.\n"
        "- **422:** Invalid input or an evaluation "
        "constraint prevented the evaluation."
    ),
    response_description=(
        "Compatibility evaluation results generated "
        "by the Compatibility Service."
    ),
    responses={
        404: {
            "description": (
                "The requested aircraft or airport "
                "could not be found."
            ),
        },
        422: {
            "description": (
                "Invalid request parameters or a "
                "compatibility evaluation error."
            ),
        },
    },
)
def evaluate_flight(
    request: Annotated[
        CompatibilityRequest,
        Body(
            description=(
                "Aircraft and route parameters required "
                "to evaluate flight compatibility."
            ),
        ),
    ],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
):
    """
    Evaluate aircraft compatibility for a proposed flight.

    Uses the Compatibility Service to evaluate a flight
    between two airports using the selected aircraft.

    Args:
        request: Flight compatibility evaluation parameters.
        catalog: Airport catalog dependency.
        db: Database session provided by FastAPI.

    Returns:
        dict:
            Compatibility evaluation results.

    Raises:
        HTTPException:
            404 when required resources cannot be found.
            422 when evaluation parameters are invalid.
    """
    service = CompatibilityService(
        airport_catalog=catalog,
        aircraft_repository=AircraftRepository(db),
    )

    try:
        result = service.evaluate_flight(
            aircraft_id=request.aircraft_id,
            departure_code=request.departure_code,
            arrival_code=request.arrival_code,
            distance_margin=request.distance_margin,
        )

        return asdict(result)

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ============================================================
# Airport Preferences
# ============================================================


@router.put(
    "/{code}/preferences",
    response_model=AirportPreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Airport Preferences",
    description=(
        "Creates or updates user-specific preferences "
        "for an airport in the Airport Catalog.\n\n"
        "Preferences are associated with the airport's "
        "ICAO identifier and persisted in the database.\n\n"
        "**Configurable preferences:**\n"
        "- **has_addon_scenery:** Whether the user has "
        "installed enhanced or third-party airport scenery.\n"
        "- **scenery_developer:** Developer responsible "
        "for the installed airport scenery.\n"
        "- **is_favourite:** Whether the airport is "
        "marked as a favourite.\n\n"
        "**Processing:**\n"
        "1. Resolves the airport using the provided code.\n"
        "2. Validates that the airport exists in the catalog.\n"
        "3. Saves the supplied preferences to the database.\n"
        "4. Commits the database transaction.\n"
        "5. Returns the saved preference values.\n\n"
        "**Important:** Omitted preference fields use "
        "their schema defaults. For example, omitting "
        "`is_favourite` sets it to `false`.\n\n"
        "Returns **404 Not Found** if the airport "
        "does not exist."
    ),
    response_description=(
        "The saved preference values for the requested airport."
    ),
    responses={
        404: {
            "description": (
                "The requested airport does not exist "
                "in the Airport Catalog."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Airport not found."
                    },
                },
            },
        },
        422: {
            "description": (
                "Invalid airport preferences request."
            ),
        },
    },
)
def update_preferences(
    code: Annotated[
        str,
        Path(
            title="Airport Code",
            description=(
                "Airport identifier used to locate the "
                "airport whose preferences will be updated."
            ),
            examples=["YBBN"],
        ),
    ],
    request: Annotated[
        PreferencesRequest,
        Body(
            description=(
                "Airport scenery and favourite preferences "
                "to save."
            ),
        ),
    ],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
):
    """
    Create or update preferences for an airport.

    Verifies that the airport exists in the catalog,
    then persists its scenery and favourite preferences.

    Args:
        code: Airport identifier.
        request: Preferences to save.
        catalog: Airport catalog dependency.
        db: Database session provided by FastAPI.

    Returns:
        AirportPreferencesResponse:
            Saved airport preference values.

    Raises:
        HTTPException:
            404 if the airport does not exist.
    """
    airport = catalog.airports.get_by_code(code)

    if airport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found.",
        )

    repository = AirportPreferencesRepository(db)

    record = repository.save(
        airport.icao_code,
        has_addon_scenery=request.has_addon_scenery,
        scenery_developer=request.scenery_developer,
        is_favourite=request.is_favourite,
    )

    db.commit()

    return {
        "icao_code": record.icao_code,
        "has_addon_scenery": record.has_addon_scenery,
        "scenery_developer": record.scenery_developer,
        "is_favourite": record.is_favourite,
    }


# ============================================================
# Airport Details
# ============================================================


@router.get(
    "/{code}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get Airport Details",
    description=(
        "Retrieves information about a specific airport "
        "from the Airport Catalog.\n\n"
        "The airport is identified using its airport code, "
        "which is resolved by the catalog provider.\n\n"
        "The response contains the airport record's "
        "available catalog data, such as identification, "
        "location, and operational information where present.\n\n"
        "**Lookup process:**\n"
        "1. Accepts the requested airport code.\n"
        "2. Searches the Airport Catalog for a matching airport.\n"
        "3. Returns the serialized airport record.\n\n"
        "Returns **404 Not Found** if the requested "
        "airport does not exist."
    ),
    response_description=(
        "Detailed airport information retrieved "
        "from the Airport Catalog."
    ),
    responses={
        404: {
            "description": (
                "No airport exists with the supplied code."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Airport not found."
                    },
                },
            },
        },
        422: {
            "description": (
                "Invalid airport lookup parameters."
            ),
        },
    },
)

@router.get("/coordinates")
def get_airport_coordinates(
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
    codes: str = Query(
        ...,
        min_length=4,
        max_length=499,
        description="Comma-separated ICAO airport codes.",
    ),
):
    """
    Return geographic coordinates for a collection
    of ICAO airport codes.

    Unknown airports are reported separately.
    """
    requested_codes = list(
        dict.fromkeys(
            code.strip().upper()
            for code in codes.split(",")
            if code.strip()
        )
    )

    if len(requested_codes) > 100:
        raise HTTPException(
            status_code=422,
            detail="Maximum 100 airports per request.",
        )

    airports = []
    missing = []
    

    for code in requested_codes:
        airport = catalog.get_by_code(code)

        if (
            airport is None
            or airport.latitude is None
            or airport.longitude is None
            or not math.isfinite(airport.latitude)
            or not math.isfinite(airport.longitude)
            or not -90 <= airport.latitude <= 90
            or not -180 <= airport.longitude <= 180
        ):
            missing.append(code)
            continue

        airports.append({
            "icao": airport.icao_code,
            "name": airport.name,
            "latitude": airport.latitude,
            "longitude": airport.longitude,
        })

    return {
        "airports": airports,
        "missing": missing,
    }

def get_airport(
    code: Annotated[
        str,
        Path(
            title="Airport Code",
            description=(
                "Airport code used to retrieve a specific "
                "airport from the Airport Catalog."
            ),
            examples=["YBBN"],
        ),
    ],
    catalog: Annotated[
        AirportCatalog,
        Depends(get_airport_catalog),
    ],
):
    """
    Retrieve detailed information about a specific airport.

    Args:
        code: Airport identifier.
        catalog: Airport catalog dependency.

    Returns:
        dict:
            Serialized airport catalog record.

    Raises:
        HTTPException:
            404 if the airport cannot be found.
    """
    airport = catalog.get_by_code(code)

    if airport is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found.",
        )

    return asdict(airport)
