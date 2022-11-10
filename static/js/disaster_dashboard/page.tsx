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
 * Main component for the disaster dashboard.
 */

import _ from "lodash";
import React, { useEffect, useRef, useState } from "react";
import { CustomInput } from "reactstrap";
import { collapseTextChangeRangesAcrossMultipleVersions } from "typescript";

import {
  EARTH_NAMED_TYPED_PLACE,
  EUROPE_NAMED_TYPED_PLACE,
  IPCC_PLACE_50_TYPE_DCID,
} from "../shared/constants";
import { NamedPlace, NamedTypedPlace } from "../shared/types";
import { loadSpinner, removeSpinner } from "../shared/util";
import { getAllChildPlaceTypes } from "../tools/map/util";
import {
  getEnclosedPlacesPromise,
  getParentPlacesPromise,
} from "../utils/place_utils";
import { CONTENT_SPINNER_ID, DISASTER_EVENT_INTENSITIES } from "./constants";
import {
  fetchDateList,
  fetchDisasterData,
  fetchGeoJsonData,
} from "./data_fetcher";
import { Map } from "./map";
import { Ranking } from "./ranking";
import { DisasterType } from "./types";

export function Page(): JSX.Element {
  const [selectedDisaster, setSelectedDisaster] = useState<DisasterType>(
    DisasterType.ALL
  );
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedPlaceInfo, setSelectedPlaceInfo] = useState({
    place: EARTH_NAMED_TYPED_PLACE,
    placeType: "Country",
    parentPlaces: [],
  });
  const [geoJsonData, setGeoJsonData] = useState(null);
  const [disasterData, setDisasterData] = useState(null);
  const [dateList, setDateList] = useState([]);
  const [breadcumbs, setBreadcrumbs] = useState([EARTH_NAMED_TYPED_PLACE]);
  const [selectedIntensityProp, setSelectedIntensityProp] = useState("");
  const europeanCountries = useRef([]);

  useEffect(() => {
    getEnclosedPlacesPromise(EUROPE_NAMED_TYPED_PLACE.dcid, "Country").then(
      (resp: Array<NamedPlace>) => {
        europeanCountries.current = resp;
      }
    );
  }, []);

  useEffect(() => {
    fetchDateList(selectedDisaster).then((dateList) => {
      setDateList(dateList);
      if (!_.isEmpty(dateList)) {
        setSelectedDate(dateList[0]);
      }
    }).catch(() => {
      setDateList([]);
      setSelectedDate("");
    });
  }, [selectedDisaster]);

  useEffect(() => {
    fetchGeoJsonData(selectedPlaceInfo.place.dcid, selectedPlaceInfo.placeType)
      .then((geoJsonData) => {
        setGeoJsonData(geoJsonData);
      })
      .catch(() => {
        setGeoJsonData({});
        window.alert(
          "Error fetching geojson data. Please try refreshing the page"
        );
      });
  }, [selectedPlaceInfo]);

  useEffect(() => {
    if (!selectedDate || !selectedPlaceInfo.place.dcid || !selectedDisaster) {
      return;
    }
    fetchDisasterData(
      selectedDisaster,
      selectedPlaceInfo.place.dcid,
      selectedDate
    )
      .then((data) => {
        setDisasterData(data);
      })
      .catch(() => {
        setDisasterData([]);
        window.alert(
          "Error fetching geojson data. Please try refreshing the page"
        );
      });
  }, [selectedPlaceInfo, selectedDisaster, selectedDate]);

  if (_.isNull(disasterData) || _.isNull(geoJsonData)) {
    return (
      <div className="screen" style={{ display: "block" }}>
        <div id="spinner"></div>
      </div>
    );
  }

  return (
    <div>
      <h1>Disaster Dashboard</h1>
      <div className="disaster-tab-section">
        {Object.values(DisasterType).map((disasterType) => {
          return (
            <div
              className={`disaster-tab${
                disasterType === selectedDisaster ? "-selected" : ""
              }`}
              onClick={() => {
                const intensityProp = !_.isEmpty(
                  DISASTER_EVENT_INTENSITIES[disasterType]
                )
                  ? DISASTER_EVENT_INTENSITIES[disasterType][0]
                  : "";
                loadSpinner(CONTENT_SPINNER_ID);
                setSelectedIntensityProp(intensityProp);
                setSelectedDate("");
                setSelectedDisaster(disasterType as DisasterType);
              }}
              key={disasterType}
            >
              {disasterType}
            </div>
          );
        })}
      </div>
      <div className="selectors-section">
        <div className="breadcrumb-section">
          {breadcumbs.map((crumb, i) => {
            return (
              <div
                key={crumb.dcid}
                className={`breadcrumb-entry${
                  i === breadcumbs.length - 1 ? "-selected" : ""
                }`}
                onClick={() => onPlaceUpdated(crumb)}
              >
                <span>{crumb.name}</span>
                {i < breadcumbs.length - 1 && (
                  <i className="material-icons-outlined">chevron_right</i>
                )}
              </div>
            );
          })}
        </div>
        <div className="date-selector-section">
          Date:
          <CustomInput
            id="date-selector"
            type="select"
            value={selectedDate}
            onChange={(e) => {
              loadSpinner(CONTENT_SPINNER_ID);
              setSelectedDate(e.target.value);
            }}
            className="pac-target-input"
          >
            {dateList.map((date) => {
              if (date === "1995-03") {
                console.log("HERE")
              }
              return <option value={date} key={date}>
                {date}
              </option>
})}
          </CustomInput>
        </div>
      </div>
      <div className="content-container">
        <Ranking
          mapPoints={disasterData}
          selectedDate={selectedDate}
          selectedDisaster={selectedDisaster}
          selectedPlace={selectedPlaceInfo.place.dcid}
          selectedIntensityProp={selectedIntensityProp}
          onIntensityPropSelected={(prop: string) =>
            setSelectedIntensityProp(prop)
          }
        />
        <Map
          mapPoints={disasterData}
          geoJson={geoJsonData}
          selectedDisaster={selectedDisaster}
          selectedDate={selectedDate}
          onPlaceUpdated={(place) =>
            onPlaceUpdated({ ...place, types: [selectedPlaceInfo.placeType] })
          }
          selectedPlaceInfo={selectedPlaceInfo}
          europeanPlaces={europeanCountries.current}
          selectedIntensityProp={selectedIntensityProp}
        />
        <div id={CONTENT_SPINNER_ID}>
          <div className="screen">
            <div id="spinner"></div>
          </div>
        </div>
      </div>
    </div>
  );

  function onPlaceUpdated(place: NamedTypedPlace): void {
    if (place.dcid === selectedPlaceInfo.place.dcid) {
      return;
    }
    loadSpinner(CONTENT_SPINNER_ID);
    getParentPlacesPromise(place.dcid).then((parentPlaces) => {
      const allChildPlaces = getAllChildPlaceTypes(place, parentPlaces).filter(
        (placeType) => placeType !== IPCC_PLACE_50_TYPE_DCID
      );
      if (!_.isEmpty(allChildPlaces)) {
        setSelectedPlaceInfo({
          place: place,
          placeType: allChildPlaces[0],
          parentPlaces,
        });
        const breadcrumbIdx = breadcumbs.findIndex(
          (crumb) => crumb.dcid === place.dcid
        );
        if (breadcrumbIdx > -1) {
          setBreadcrumbs(breadcumbs.slice(0, breadcrumbIdx + 1));
        } else {
          setBreadcrumbs([...breadcumbs, place]);
        }
      } else {
        removeSpinner(CONTENT_SPINNER_ID);
        window.alert("Sorry, we do not have maps for this place");
      }
    });
  }
}
