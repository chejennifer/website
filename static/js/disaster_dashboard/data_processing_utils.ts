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
import _ from "lodash";

import { MapPoint } from "../chart/types";
import { EARTH_NAMED_TYPED_PLACE } from "../shared/constants";
import { DISASTER_EVENT_INTENSITIES } from "./constants";
import { DisasterEventPoint, DisasterType } from "./types";

export function processMapPoints(
  mapPointData: DisasterEventPoint[],
  selectedDisaster: DisasterType,
  selectedDate: string,
  selectedPlace: string,
  selectedProp: string
): { points: MapPoint[]; values: { [eventDcid: string]: number } } {
  const points = [];
  const values = {};
  for (const place in mapPointData) {
    points.push({
      ...mapPointData[place],
      placeDcid: place,
      placeName: place,
    });
    if (selectedProp in mapPointData[place].intensity) {
      values[place] = mapPointData[place].intensity[selectedProp];
    }
  }
  return { points, values };
}

interface RankingUnitInfo {
  title: string;
  prop: string;
  ranking: DisasterEventPoint[];
}

export function processRankings(
  mapPointData: DisasterEventPoint[],
  selectedDisaster: DisasterType
): RankingUnitInfo[] {
  const rankings = [];
  const props = DISASTER_EVENT_INTENSITIES[selectedDisaster] || [];
  if (_.isEmpty(mapPointData)) {
    return rankings;
  }
  for (const prop of props) {
    const sortedEvents = mapPointData.sort((a, b) => {
      const eventDataAVal = a.intensity[prop];
      const eventDataBVal = b.intensity[prop];
      if (eventDataAVal && eventDataBVal) {
        return eventDataBVal - eventDataAVal;
      } else if (eventDataAVal) {
        return -1;
      } else {
        return 0;
      }
    });
    rankings.push({
      title: prop,
      prop,
      ranking: sortedEvents,
    });
  }
  return rankings;
}
