# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Build the embeddings index by concatenating various inputs."""

# TODO: Consider adding the model name to the embeddings file for downstream
# validation.

import csv
import os
import time

from absl import app
from absl import flags
import gspread
import pandas as pd
import requests

FLAGS = flags.FLAGS
_TEMP_DIR = "/tmp"
_DEFAULT_OUTPUT_LOCAL_CSV_FILE = "sheets2csv.csv"
_DEFAULT_SHEET_NAME = "Csv2Sheet"
_NEW_SHEET_ROWS_COLS_BUFFER = 5
NODE_API_URL = f'https://api.datacommons.org/v2/node?key=FnbaAdwtSMqmgXTmEBiJUyfH39h2szxp2eVPVKlcQGdAphen'
seen_svgs = set()

class Mode:
  CSV_TO_SHEET = "csv2sheet"
  SHEET_TO_CSV = "sheet2csv"
  SV_HIERARCHY = "svHierarchy"


flags.DEFINE_string('local_csv_filepath',
                    '',
                    'Local csv (relative) file path',
                    short_name='l')
flags.DEFINE_string('sheets_url',
                    '',
                    'Google Sheets Url for the latest SVs',
                    short_name='s')
flags.DEFINE_string('worksheet_name',
                    '',
                    'Name of worksheet in the Google Sheets file to use',
                    short_name='w')
flags.DEFINE_enum(
    'mode',
    Mode.CSV_TO_SHEET,
    [Mode.CSV_TO_SHEET, Mode.SHEET_TO_CSV, Mode.SV_HIERARCHY],
    'Mode of operation to use. Valid values: sheet2csv, csv2sheet',
    short_name='m')


# Copies a csv file to a Google Sheets worksheet
def csv2sheet(local_csv_filepath: str, sheets_url: str, worksheet_name: str):
  gs = gspread.oauth()
  worksheet = None
  if sheets_url:
    # If url to a sheet is provided, use that sheet
    sheet = gs.open_by_url(sheets_url)
    if worksheet_name:
      # If worksheet name is also provided, use that worksheet. Otherwise, need
      # to create worksheet once we know how many rows and columns to add.
      worksheet = sheet.worksheet(worksheet_name)
  else:
    # Otherwise, create new sheet and use the first worksheet, which gets
    # created with the sheet
    sheet = gs.create(worksheet_name or _DEFAULT_SHEET_NAME)
    worksheet = sheet.get_worksheet(0)

  with open(local_csv_filepath, 'r') as f:
    print(f"Copying CSV file data to Google Sheets from: {local_csv_filepath}")
    reader = csv.reader(f)
    rows = list(reader)
    if not worksheet:
      num_cols = 0
      if len(rows) > 0:
        num_cols = len(rows[0]) + _NEW_SHEET_ROWS_COLS_BUFFER
      worksheet = sheet.add_worksheet(_DEFAULT_SHEET_NAME,
                                      len(rows) + _NEW_SHEET_ROWS_COLS_BUFFER,
                                      num_cols)
    worksheet.update('A1', rows)
  print(
      f"CSV file data copied to {sheet.title}: {sheet.url} (worksheet: {worksheet.title})"
  )


# Copies a Google Sheets worksheet to a csv file.
def sheet2csv(sheets_url: str, worksheet_name: str, local_csv_filepath: str):
  gs = gspread.oauth()
  print(
      f"Downloading the latest sheets data from: {sheets_url} (worksheet: {worksheet_name})"
  )
  sheet = gs.open_by_url(sheets_url).worksheet(worksheet_name)
  # Fill empty cells with an empty string so that it reflects how the sheet looks.
  worksheet_df = pd.DataFrame(sheet.get_all_records()).fillna("")
  print(
      f"Downloaded {len(worksheet_df)} rows and {len(worksheet_df.columns)} columns."
  )
  worksheet_df.to_csv(local_csv_filepath, index=False)
  print(f"Dataframe saved locally at: {local_csv_filepath}")


def update_cell(ws, row, col, val):
  try:
    time.sleep(1)
    if row % 250 == 0:
      print(f'populating row {row}')
    ws.update_cell(row, col, val)
    return True
  except:
    return False


def get(req):
  attempts = 1
  resp = None
  while not resp or resp.status_code != 200:
    if attempts > 3:
      break
    try:
      resp = requests.get(req, timeout=10)
    except:
      resp = None
    attempts += 1
  return resp


def get_nodes(nodes, prop):
  resp = get(f'{NODE_API_URL}&nodes={nodes}&property={prop}')
  if not resp:
    return None
  resp = resp.json()
  result = {}
  for d, item in resp.get('data', {}).items():
    for prop, prop_item in item.get('arcs', {}).items():
      if d not in result:
        result[d] = {}
      if prop not in result[d]:
        result[d][prop] = []
      result[d][prop].extend(prop_item.get('nodes', []))
  next_token = result.get('nextToken', '')
  while next_token:
    next_result = get(
        f'{NODE_API_URL}&nodes={nodes}&property={prop}&nextToken={next_token}')
    if not next_result:
      return None
    next_result = next_result.json()
    next_token = next_result.get('nextToken', '')
    for d, item in next_result.get('data', {}).items():
      for prop, prop_item in item.get('arcs', {}).items():
        if d not in result:
          result[d] = {}
        if prop not in result[d]:
          result[d][prop] = []
        result[d][prop].extend(prop_item.get('nodes', []))
  return result


def populate_hierarchy_sheets(ws, starting_row, dcid, name, level, row_to_start=0):
  if starting_row % 250 == 0:
    print(f'working on row {starting_row}')
  sv_members = get_nodes(dcid, '%3C-memberOf')
  svg_members = get_nodes(dcid, '%3C-specializationOf')
  if sv_members == None or svg_members == None:
    print(f'FAILED: {dcid} ({name}) @ {starting_row}')
    return starting_row
  sv_members = sv_members.get(dcid, {}).get('memberOf', [])
  svg_members = svg_members.get(dcid, {}).get('specializationOf', [])
  if starting_row >= row_to_start:
    if not update_cell(
        ws, starting_row, level + 1,
        f'=HYPERLINK("https://datacommons.org/browser/{dcid}", "{dcid}\n{name}")'
    ):
      print(f'FAILED: {dcid} ({name}) @ {starting_row}')
      return starting_row
  curr_row = starting_row + 1
  for sv in sv_members:
    sv_dcid = sv.get('dcid')
    sv_name = sv.get('name')
    if curr_row >= row_to_start:
      if not update_cell(
          ws, curr_row, level + 2,
          f'=HYPERLINK("https://datacommons.org/browser/{sv_dcid}", "{sv_dcid}\n{sv_name}")'
      ):
        print(f'FAILED: {sv_dcid} ({sv_name}) @ {curr_row}')
    curr_row += 1
  for svg in svg_members:
    svg_dcid = svg.get('dcid')
    curr_row = populate_hierarchy(ws, curr_row, svg_dcid, svg.get('name'),
                                  level + 1, row_to_start)
  return curr_row


def write_to_csv(writer, dcid, name, level):
  data = []
  for i in range(30):
    if i == level:
      data.append(f'"=HYPERLINK("https://datacommons.org/browser/{dcid}", "{dcid}\n{name}")"')
    else:
      data.append('')
  try:
    writer.writerow(data)
    return True
  except Exception as e:
    print(f'exception writing: {e}')
    return False


def populate_hierarchy(csv_writer, starting_row, dcid, name, level, added, row_to_start=0):
  global seen_svgs
  if dcid in seen_svgs:
    return starting_row
  if starting_row % 250 == 0:
    print(f'working on row {starting_row}')
  sv_members = get_nodes(dcid, '%3C-memberOf')
  svg_members = get_nodes(dcid, '%3C-specializationOf')
  if starting_row >= row_to_start:
    if not write_to_csv(
        csv_writer, dcid, name, level
    ):
      print(f'FAILED ADDING: {dcid} ({name}) @ {starting_row}')
      return starting_row
  seen_svgs.add(dcid)
  curr_row = starting_row + 1
  if sv_members == None:
    print(f'NO SV MEMBERS: {dcid} ({name}) @ {starting_row}')
    sv_members = []
  else:
    sv_members = sv_members.get(dcid, {}).get('memberOf', [])
  if svg_members == None:
    print(f'NO SVG MEMBERS: {dcid} ({name}) @ {starting_row}')
    svg_members = []
  else:
    svg_members = svg_members.get(dcid, {}).get('specializationOf', [])
  for sv in sv_members:
    sv_dcid = sv.get('dcid')
    sv_name = sv.get('name')
    if curr_row >= row_to_start:
      if not write_to_csv(
          csv_writer, sv_dcid, sv_name, level + 1):
        print(f'FAILED ADDING: {sv_dcid} ({sv_name}) @ {curr_row}')
    curr_row += 1
  for svg in svg_members:
    svg_dcid = svg.get('dcid')
    curr_row = populate_hierarchy(csv_writer, curr_row, svg_dcid, svg.get('name'),
                                  level + 1, added, row_to_start)
  return curr_row


def generate_sv_hierarchy(sheets_url: str):
  #gs = gspread.oauth()
  #sheet = gs.open_by_url(sheets_url)
  for svg in [{
      'dcid': 'dc/g/Demographics',
      'name': 'Demographics',
      'rows': 8000,
      'row_to_start': 0
  }, {
      'dcid': 'dc/g/Health',
      'name': 'Health',
      'rows': 8000,
      'row_to_start': 0
  }, {
      'dcid': 'dc/g/Economy',
      'name': 'Economy',
      'rows': 8000,
      'row_to_start': 0
  }, {
      'dcid': 'dc/g/Education',
      'name': 'Education',
      'rows': 8000,
      'row_to_start': 0
  }]:
    svg_name = svg.get('name')
    svg_dcid = svg.get('dcid')
    global seen_svgs
    seen_svgs = set()
    print(f'populating {svg_name}')
    with open(f'output_{svg_name}.csv', mode='w', newline='') as file:
      writer = csv.writer(file)
      end_row = populate_hierarchy(writer, 1, svg_dcid, svg_name, 0, set(),
                                  svg.get('row_to_start', 0))
    # try:
    #   ws = sheet.worksheet(svg_name)
    # except gspread.exceptions.WorksheetNotFound:
    #   ws = sheet.add_worksheet(svg_name, rows=svg['rows'], cols=30)
    # end_row = populate_hierarchy(ws, 1, svg_dcid, svg_name, 0,
    #                              svg.get('row_to_start', 0))
    print(f'finished populating {svg_name}')
    print(f'last row: {end_row}')


def main(_):
  if FLAGS.mode == Mode.SHEET_TO_CSV:
    assert FLAGS.sheets_url and FLAGS.worksheet_name
    local_csv_filepath = FLAGS.local_csv_filepath or os.path.join(
        _TEMP_DIR, _DEFAULT_OUTPUT_LOCAL_CSV_FILE)
    sheet2csv(FLAGS.sheets_url, FLAGS.worksheet_name, local_csv_filepath)
  elif FLAGS.mode == Mode.CSV_TO_SHEET:
    assert FLAGS.local_csv_filepath
    csv2sheet(FLAGS.local_csv_filepath, FLAGS.sheets_url, FLAGS.worksheet_name)
  else:
    generate_sv_hierarchy(FLAGS.sheets_url)


if __name__ == "__main__":
  app.run(main)
