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
import React from "react";

import { DISASTER_EVENT_INTENSITIES, DISASTER_EVENT_TYPES } from "./constants";
import { processRankings } from "./data_processing_utils";
import { DisasterEventPoint, DisasterType } from "./types";

const RANKING_ITEMS_COUNT = 5;
interface RankingPropType {
  mapPoints: DisasterEventPoint[];
  selectedDisaster: DisasterType;
  selectedDate: string;
  selectedPlace: string;
  selectedIntensityProp: string;
  onIntensityPropSelected: (prop: string) => void;
}

export function Ranking(props: RankingPropType): JSX.Element {
  const counts = {};
  if (!_.isEmpty(props.mapPoints)) {
    for (const event in props.mapPoints) {
      const point = props.mapPoints[event];
      if (!(point.disasterType in counts)) {
        counts[point.disasterType] = 0;
      }
      counts[point.disasterType]++;
    }
  }
  const rankedDisasters = Object.keys(DISASTER_EVENT_TYPES).sort((a, b) => {
    if (counts[b] && counts[a]) {
      return counts[b] - counts[a];
    } else if (counts[b]) {
      return 1;
    } else {
      return -1;
    }
  });
  const rankingUnits = processRankings(props.mapPoints, props.selectedDisaster);
  const addSelectionCss =
    !_.isEmpty(DISASTER_EVENT_INTENSITIES[props.selectedDisaster]) &&
    DISASTER_EVENT_INTENSITIES[props.selectedDisaster].length > 1;
  const getRankingUnitClassName = (prop: string) => {
    if (!addSelectionCss) {
      return "ranking-unit-no-selection";
    }
    return prop === props.selectedIntensityProp
      ? "ranking-unit-selected"
      : "ranking-unit";
  };
  return (
    <div className="ranking-section">
      {props.selectedDisaster === DisasterType.ALL && (
        <>
          <h3>Count of Events</h3>
          {rankedDisasters.map((dType) => {
            return (
              <div key={"count-" + dType} className="ranking-unit-item">
                {dType}: {counts[dType] || 0}
              </div>
            );
          })}
        </>
      )}
      {(!_.isEmpty(rankingUnits) ||
        props.selectedDisaster !== DisasterType.ALL) && (
        <>
          <h3>Rankings</h3>
          {rankingUnits.map((rankingUnit) => {
            return (
              <div
                onClick={() => props.onIntensityPropSelected(rankingUnit.prop)}
                className={getRankingUnitClassName(rankingUnit.prop)}
                key={rankingUnit.prop}
              >
                <div className={"ranking-unit-title"}>{rankingUnit.title}</div>
                {rankingUnit.ranking
                  .slice(0, RANKING_ITEMS_COUNT)
                  .map((event) => {
                    return (
                      <div
                        key={`${rankingUnit.prop}-${event.placeDcid}`}
                        className="ranking-unit-item"
                      >
                        {event.placeName}: {event.intensity[rankingUnit.prop]}
                      </div>
                    );
                  })}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
