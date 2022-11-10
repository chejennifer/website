/**
 * Copyright 2022 Google LLC
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
 * Functions that return promises for data needed for disaster dashbaord
 */

import axios from "axios";
import _, { result } from "lodash";

import { GeoJsonData } from "../chart/types";
import { EARTH_NAMED_TYPED_PLACE } from "../shared/constants";
import { DISASTER_EVENT_INTENSITIES, DISASTER_EVENT_TYPES } from "./constants";
import { DisasterEventPoint, DisasterType } from "./types";

export const LOCATION_PROPS = ["location", "affectedPlace", "startLocation"];
export const LAT_PROP = "latitude";
export const LNG_PROP = "longitude";
const LAT_LNG_DCID_PREFIX = "latLong";
export const START_DATE_PROPS = [
  "occurrenceTime",
  "discoveryDate",
  "startDate",
];
export const END_DATE_PROPS = ["endDate"];
export const NAME_PROPS = ["name"];

export function fetchGeoJsonData(
  selectedPlace: string,
  placeType: string
): Promise<GeoJsonData> {
  return axios
    .get("/api/choropleth/geojson", {
      params: {
        placeDcid: selectedPlace,
        placeType: placeType,
      },
    })
    .then((resp) => resp.data as GeoJsonData);
}

export function fetchDateList(disasterType: DisasterType): Promise<string[]> {
  const promises = [];
  const disasterTypesToFetch =
    disasterType === DisasterType.ALL
      ? Object.keys(DISASTER_EVENT_TYPES)
      : [disasterType];
  for (const disasterType of disasterTypesToFetch) {
    DISASTER_EVENT_TYPES[disasterType].forEach((eventType) => {
      promises.push(
        axios
          .get("/api/disaster-dashboard/date-range", {
            params: {
              eventType,
            },
          })
          .then((resp) => resp.data)
      );
    });
  }
  return Promise.all(promises).then((resp) => {
    let minDate = "";
    let maxDate = "";
    resp.forEach((dateRange) => {
      if (dateRange.minDate) {
        if (!minDate || dateRange.minDate < minDate) {
          minDate = dateRange.minDate;
        }
        if (!maxDate || dateRange.minDate > maxDate) {
          maxDate = dateRange.maxDate;
        }
      }
      if (!maxDate || dateRange.maxDate > maxDate) {
        maxDate = dateRange.maxDate;
      }
    });
    if (!minDate && !maxDate) {
      return [];
    }
    let decrementByYear = false;
    if (
      new Date(maxDate).getFullYear() - new Date(minDate).getFullYear() >
      100
    ) {
      decrementByYear = true;
    }
    const dateList = [];
    const currDate = new Date(maxDate);
    const endDate = new Date(minDate);
    while (currDate >= endDate) {
      const stringCut = decrementByYear ? 4 : 7;
      dateList.push(currDate.toISOString().substring(0, stringCut));
      if (decrementByYear) {
        currDate.setFullYear(currDate.getFullYear() - 1);
      } else {
        currDate.setMonth(currDate.getMonth() - 1);
      }
    }
    return dateList;
  });
}

function fetchEventTypeData(
  eventType: string,
  place: string,
  date: string,
  disasterType: DisasterType
): Promise<DisasterEventPoint[]> {
  return axios
    .get("/api/disaster-dashboard/data", {
      params: {
        eventType: eventType,
        place: place,
        date: date,
      },
    })
    .then((resp) => {
      const result = [];
      resp.data.forEach((eventData) => {
        const intensity = {};
        if (disasterType in DISASTER_EVENT_INTENSITIES) {
          for (const prop of DISASTER_EVENT_INTENSITIES[disasterType]) {
            if (prop in eventData) {
              intensity[prop] = eventData[prop];
            }
          }
        }
        result.push({
          placeDcid: eventData.eventId,
          placeName: eventData.name || eventData.eventId,
          latitude: eventData.latitude,
          longitude: eventData.longitude,
          disasterType,
          startDate: eventData.startDate,
          intensity,
          endDate: eventData.endDate,
        });
      });
      return result;
    });
}

export function fetchDisasterData(
  disasterType: DisasterType,
  place: string,
  date: string
): Promise<DisasterEventPoint[]> {
  const eventTypeToDisasterType = {};
  const dates = [];
  if (date.length === 4) {
    for (let i = 1; i < 13; i++) {
      dates.push(`${date}-${i < 10 ? "0" : ""}${i}`);
    }
  } else if (date.length === 7) {
    dates.push(date);
  }
  let eventTypes = [];
  if (disasterType === DisasterType.ALL) {
    for (const dType in DISASTER_EVENT_TYPES) {
      eventTypes = eventTypes.concat(DISASTER_EVENT_TYPES[dType]);
      DISASTER_EVENT_TYPES[dType].forEach((eventType) => {
        eventTypeToDisasterType[eventType] = dType;
      });
    }
  } else {
    eventTypes = DISASTER_EVENT_TYPES[disasterType];
    eventTypes.forEach((eventType) => {
      eventTypeToDisasterType[eventType] = disasterType;
    });
  }
  const promises = [];
  for (const eventType of eventTypes) {
    for (const date of dates) {
      const disasterType = eventTypeToDisasterType[eventType];
      promises.push(fetchEventTypeData(eventType, place, date, disasterType));
    }
  }
  return Promise.all(promises).then((resp) => {
    let result = [];
    resp.forEach((eventTypeResp) => {
      result = result.concat(eventTypeResp);
    });
    return result;
  });
}
