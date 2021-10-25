/**
 * Copyright 2021 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Utility functions shared across different components of map explorer.
 */

import _ from "lodash";

import { INDIA_PLACE_DCID } from "../../shared/constants";
import { NamedPlace } from "../../shared/types";
import { isChildPlaceOf } from "../shared_util";
import { DisplayOptions, NamedTypedPlace, PlaceInfo, StatVar } from "./context";

const USA_STATE_CHILD_TYPES = ["County"];
const USA_COUNTRY_CHILD_TYPES = ["State", ...USA_STATE_CHILD_TYPES];
export const DEFAULT_DENOM = "Count_Person";

export const CHILD_PLACE_TYPES = {
  Planet: ["Country"],
  Continent: ["Country"],
  Country: USA_COUNTRY_CHILD_TYPES,
  State: USA_STATE_CHILD_TYPES,
  County: ["County"],
  AdministrativeArea1: ["AdministrativeArea2"],
  AdministrativeArea2: ["AdministrativeArea2"],
  EurostatNUTS1: ["EurostatNUTS2", "EurostatNUTS3"],
  EurostatNUTS2: ["EurostatNUTS3"],
  EurostatNUTS3: ["EurostatNUTS3"],
};

export const INDIA_PLACE_TYPES = {
  AdministrativeArea1: "AdministrativeArea1",
  AdministrativeArea2: "AdministrativeArea2",
  County: "AdministrativeArea2",
  State: "AdministrativeArea1",
};

export const EUROPE_CHILD_PLACE_TYPES = {
  Continent: ["Country", "EurostatNUTS1", "EurostatNUTS2", "EurostatNUTS3"],
  Country: ["EurostatNUTS1", "EurostatNUTS2", "EurostatNUTS3"],
  EurostatNUTS1: ["EurostatNUTS2", "EurostatNUTS3"],
  EurostatNUTS2: ["EurostatNUTS3"],
  EurostatNUTS3: ["EurostatNUTS3"],
};

// list of place types in the US in the order of high to low granularity.
export const USA_PLACE_HIERARCHY = ["Country", "State", "County"];

const URL_PARAM_VALUE_SEPARATOR = "-";

const URL_PARAM_KEYS = {
  SELECTED_PLACE_DCID: "pd",
  SELECTED_PLACE_NAME: "pn",
  SELECTED_PLACE_TYPES: "pt",
  ENCLOSED_PLACE_TYPE: "ept",
  MAP_POINTS_PLACE_TYPE: "ppt",
  PER_CAPITA: "pc",
  STAT_VAR_DCID: "sv",
  DATE: "dt",
  COLOR: "color",
  DOMAIN: "domain",
  DENOM: "denom",
};

export const MAP_REDIRECT_PREFIX = "/tools/map";

/**
 * Parses the hash and produces a StatVar
 * @param params the params in the hash
 */
export function applyHashStatVar(params: URLSearchParams): StatVar {
  const dcid = params.get(URL_PARAM_KEYS.STAT_VAR_DCID);
  const date = params.get(URL_PARAM_KEYS.DATE);
  const denom = params.get(URL_PARAM_KEYS.DENOM);
  if (!dcid) {
    return { dcid: "", perCapita: false, info: null, date: "", denom: "" };
  }
  const perCapita = params.get(URL_PARAM_KEYS.PER_CAPITA);
  return {
    dcid,
    perCapita: perCapita && perCapita === "1" ? true : false,
    info: null,
    date: date ? date : "",
    denom: denom ? denom : DEFAULT_DENOM,
  };
}

/**
 * Parses the hash and produces a PlaceInfo
 * @param params the params in the hash
 */
export function applyHashPlaceInfo(params: URLSearchParams): PlaceInfo {
  const selectedPlaceDcid = params.get(URL_PARAM_KEYS.SELECTED_PLACE_DCID);
  const selectedPlaceName = params.get(URL_PARAM_KEYS.SELECTED_PLACE_NAME);
  const selectedPlaceTypes = params.get(URL_PARAM_KEYS.SELECTED_PLACE_TYPES);
  const enclosedPlaceType = params.get(URL_PARAM_KEYS.ENCLOSED_PLACE_TYPE);
  const mapPointsPlaceType = params.get(URL_PARAM_KEYS.MAP_POINTS_PLACE_TYPE);
  return {
    selectedPlace: {
      dcid: selectedPlaceDcid ? selectedPlaceDcid : "",
      name: selectedPlaceName ? selectedPlaceName : "",
      types: selectedPlaceTypes
        ? selectedPlaceTypes.split(URL_PARAM_VALUE_SEPARATOR)
        : [],
    },
    enclosingPlace: {
      dcid: "",
      name: "",
    },
    enclosedPlaces: [],
    enclosedPlaceType: enclosedPlaceType ? enclosedPlaceType : "",
    parentPlaces: null,
    mapPointsPlaceType: mapPointsPlaceType ? mapPointsPlaceType : "",
  };
}

/**
 * Parses the hash and produces a DisplayOptions
 * @param params the params in the hash
 */
export function applyHashDisplay(params: URLSearchParams): DisplayOptions {
  const color = params.get(URL_PARAM_KEYS.COLOR);
  const domainParamValue = params.get(URL_PARAM_KEYS.DOMAIN);
  const domain = domainParamValue
    ? domainParamValue
        .split(URL_PARAM_VALUE_SEPARATOR)
        .map((val) => Number(val))
    : [];
  return {
    color,
    domain: domain.length === 3 ? (domain as [number, number, number]) : null,
  };
}

/**
 * Updates the hash based on a StatVar and returns the new hash
 * @param hash the current hash
 * @param statVar the StatVar to update the hash with
 */
export function updateHashStatVar(hash: string, statVar: StatVar): string {
  if (_.isEmpty(statVar.dcid)) {
    return hash;
  }
  const perCapita = statVar.perCapita ? "1" : "0";
  const dateParam = statVar.date
    ? `&${URL_PARAM_KEYS.DATE}=${statVar.date}`
    : "";
  const params =
    `&${URL_PARAM_KEYS.STAT_VAR_DCID}=${statVar.dcid}` +
    `&${URL_PARAM_KEYS.PER_CAPITA}=${perCapita}` +
    `&${URL_PARAM_KEYS.DENOM}=${statVar.denom}` +
    dateParam;
  return hash + params;
}

/**
 * Updates the hash based on a PlaceInfo and returns the new hash
 * @param hash the current hash
 * @param placeInfo the PlaceInfo to update the hash with
 */
export function updateHashPlaceInfo(
  hash: string,
  placeInfo: PlaceInfo
): string {
  if (_.isEmpty(placeInfo.selectedPlace.dcid)) {
    return hash;
  }
  const selectedPlaceTypes = !_.isEmpty(placeInfo.selectedPlace.types)
    ? placeInfo.selectedPlace.types.join(URL_PARAM_VALUE_SEPARATOR)
    : "";
  let params =
    `&${URL_PARAM_KEYS.SELECTED_PLACE_DCID}=${placeInfo.selectedPlace.dcid}` +
    `&${URL_PARAM_KEYS.SELECTED_PLACE_NAME}=${placeInfo.selectedPlace.name}` +
    `&${URL_PARAM_KEYS.SELECTED_PLACE_TYPES}=${selectedPlaceTypes}`;
  if (!_.isEmpty(placeInfo.enclosedPlaceType)) {
    params = `${params}&${URL_PARAM_KEYS.ENCLOSED_PLACE_TYPE}=${placeInfo.enclosedPlaceType}`;
  }
  if (!_.isEmpty(placeInfo.mapPointsPlaceType)) {
    params = `${params}&${URL_PARAM_KEYS.MAP_POINTS_PLACE_TYPE}=${placeInfo.mapPointsPlaceType}`;
  }
  return hash + params;
}

/**
 * Updates the hash based on DisplayOptions and returns the new hash
 * @param hash the current hash
 * @param placeInfo the DisplayOptions to update the hash with
 */
export function updateHashDisplay(
  hash: string,
  display: DisplayOptions
): string {
  let params = "";
  if (display.color) {
    params = `${params}&${URL_PARAM_KEYS.COLOR}=${display.color}`;
  }
  if (display.domain) {
    params = `${params}&${URL_PARAM_KEYS.DOMAIN}=${display.domain.join(
      URL_PARAM_VALUE_SEPARATOR
    )}`;
  }
  return hash + params;
}

/**
 * Get the default enclosed place type for a given place
 * @param selectedPlace place to get enclosed place type for
 * @param isIndiaPlace whether the place we're getting enclosed place type for is in India
 */
function getEnclosedPlaceType(
  selectedPlace: NamedTypedPlace,
  isIndiaPlace: boolean
): string {
  for (const type of selectedPlace.types) {
    if (type in CHILD_PLACE_TYPES) {
      let enclosedPlacetypes = CHILD_PLACE_TYPES[type];
      if (isIndiaPlace) {
        enclosedPlacetypes = enclosedPlacetypes
          .filter((type) => type in INDIA_PLACE_TYPES)
          .map((type) => INDIA_PLACE_TYPES[type]);
      }
      if (enclosedPlacetypes.length >= 1) {
        return enclosedPlacetypes[0];
      }
    }
  }
  return "";
}

/**
 * Get the link to the map explorer page for a given place and stat var
 * @param statVar the stat var of the map page to redirect to
 * @param selectedPlace the place of the map page to redirect to
 * @param parentPlaces the parent places of the place we are redirecting to
 * @param mapPointsPlaceType the map points place type of the map page to redirect to
 */
export function getRedirectLink(
  statVar: StatVar,
  selectedPlace: NamedTypedPlace,
  parentPlaces: NamedPlace[],
  mapPointsPlaceType: string
): string {
  let hash = updateHashStatVar("", statVar);
  const parentPlacesList = _.cloneDeep(parentPlaces);
  const idxInParentPlaces = parentPlaces.findIndex(
    (parentPlace) => parentPlace.dcid === selectedPlace.dcid
  );
  if (idxInParentPlaces > -1) {
    parentPlacesList.splice(parentPlaces.length - 1 - idxInParentPlaces);
  }
  const enclosedPlaceType = getEnclosedPlaceType(
    selectedPlace,
    isChildPlaceOf(selectedPlace.dcid, INDIA_PLACE_DCID, parentPlacesList)
  );
  hash = updateHashPlaceInfo(hash, {
    enclosedPlaces: [],
    enclosedPlaceType,
    enclosingPlace: { dcid: "", name: "" },
    mapPointsPlaceType,
    parentPlaces: [],
    selectedPlace,
  });
  return `${MAP_REDIRECT_PREFIX}#${encodeURIComponent(hash)}`;
}

/**
 * Get all the possible child place types for a given place type
 * @param type the place type to get the child place types for
 */
export function getAllChildPlaceTypes(type: string): string[] {
  const childTypes = CHILD_PLACE_TYPES[type];
  if (_.isEmpty(childTypes)) {
    return [];
  }
  const uniquePlaceTypes: Set<string> = new Set(childTypes);
  childTypes
    .filter((childType) => childType in INDIA_PLACE_TYPES)
    .forEach((childType) => uniquePlaceTypes.add(INDIA_PLACE_TYPES[childType]));
  return Array.from(uniquePlaceTypes);
}
