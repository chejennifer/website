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

# TODO: Consider adding the model name to the embeddings file for downstream
# validation.

import datetime
import re
import time

from absl import app
from absl import flags
from dateutil.relativedelta import relativedelta
import gspread
import requests

FLAGS = flags.FLAGS
flags.DEFINE_string('sheets_url',
                    '',
                    'Google Sheets Url for the latest SVs',
                    short_name='s')

_QUERY_TYPE_COLUMN = 2
_QUERY_COLUMN = 3
_PLACE_QUERY_COLUMN = 8
_PLACE_COLUMN = 9
_CONCEPTS_COLUMN = 10
_SVG_COLUMN = 13
_SVG_COLUMN_2 = 14
_SV_COLUMN = 15
_SV_SENTENCE_COLUMN = 16
_OTHER_CLASSIFICATIONS_QUERY_COLUMN = 7
_OTHER_CLASSIFICATIONS_VARIABLE_COLUMN = 12
_CLASSIFICATION_TYPE_QUERY = 'Query'
_CLASSIFICATION_TYPE_VARIABLE = 'Variable'
_CLASSIFICATION_COLUMNS = {
    'contained_in_classification': {
        'val': 4
    },
    'date_classification': {
        'start': 5,
        'end': 6,
    },
    'quantity_classification': {
        'val': 11
    },
}

_CLASSIFICATION_VAL_MAPPING = {
    'comparison_classification': {
        'DETECTED': {
            'type': _CLASSIFICATION_TYPE_QUERY,
            'classifier': 'comparison_classification',
            'val': 'Detected',
        }
    },
    'correlation_classification': {
        'DETECTED': {
            'type': _CLASSIFICATION_TYPE_QUERY,
            'classifier': 'correlation_classification',
            'val': 'Detected',
        }
    },
    'general_classification': {
        'Per Capita': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'general_classification',
            'val': 'Per Capita',
        },
        'Overview': {
            'type': _CLASSIFICATION_TYPE_QUERY,
            'classifier': 'general_classification',
            'val': 'Overview',
        },
        'Answer Places Reference': {
            'type': _CLASSIFICATION_TYPE_QUERY,
            'classifier': 'general_classification',
            'val': 'Answer Places Reference',
        }
    },
    'ranking_classification': {
        'RankingType.HIGH': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'High',
        },
        'RankingType.LOW': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'Low',
        },
        'RankingType.BEST': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'High',
        },
        'RankingType.WORST': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'Low',
        },
    },
    'superlative_classification': {
        'SuperlativeType.BIG': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'High',
        },
        'SuperlativeType.SMALL': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'Low',
        },
        'SuperlativeType.RICH': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'High',
        },
        'SuperlativeType.POOR': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'ranking_classification',
            'val': 'Low',
        },
        'SuperlativeType.LIST': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'list_classification',
            'val': 'Detected',
        },
    },
    'time_delta_classification': {
        'TimeDeltaType.INCREASE': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'time_delta_classification',
            'val': 'Increase',
        },
        'TimeDeltaType.DECREASE': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'time_delta_classification',
            'val': 'Decrease',
        },
        'TimeDeltaType.CHANGE': {
            'type': _CLASSIFICATION_TYPE_VARIABLE,
            'classifier': 'time_delta_classification',
            'val': 'Change',
        },
    }
}

_SVG_DCID_MAPPING = {
    'dc/g/Demographics': 'Demographics',
    'dc/g/Agriculture': 'Agriculture',
    'dc/g/Crime': 'Crime',
    'dc/g/Economy': 'Economy',
    'dc/g/Education': 'Education',
    'dc/g/Environment': 'Environment',
    'dc/g/Health': 'Health',
    'dc/g/Housing': 'Housing',
    'dc/g/SDG': 'SDG',
}
DC_API_KEY = 'FnbaAdwtSMqmgXTmEBiJUyfH39h2szxp2eVPVKlcQGdAphen'
NODE_API_URL = f'https://api.datacommons.org/v2/node?key={DC_API_KEY}'
# Placeholder prep to use for LAST_YEAR/LAST_YEARS type dates because they do
# not depend on the preposition and should all be treated the same way.
_LAST_YEARS_PREP = 'last_years'
# List of date preps that indicate that the base date is a start date
_START_DATE_PREPS = ['after', 'since', 'from', _LAST_YEARS_PREP]
# List of date preps that indicate that the base date is an end date
_END_DATE_PREPS = ['before', 'by', 'until']
# List of date preps that exclude the base date
_EXCLUSIVE_DATE_PREPS = ['before', 'after']
_MIN_MONTH = 1
_MIN_DOUBLE_DIGIT_MONTH = 10


def get(req):
  resp = requests.get(req)
  attempts = 1
  while resp.status_code != 200 and attempts < 3:
    time.sleep(5)
    resp = requests.get(req)
    attempts += 1
  return resp


def _get_month_string(month: int) -> str:
  month_string = ''
  if month >= _MIN_DOUBLE_DIGIT_MONTH:
    month_string = f'-{month}'
  elif month >= _MIN_MONTH:
    month_string = f'-0{month}'
  return month_string


def _get_base_year_month(prep, year, month, year_span):
  base_year = year
  base_month = month
  # if date range excludes the specified date, need to do some calculations to
  # get the base date.
  if prep in _EXCLUSIVE_DATE_PREPS:
    # if specified date is an end date, base date should be earlier than
    # specified date
    if prep in _END_DATE_PREPS:
      # if date is monthly, use date that is one month before the specified date
      if base_month >= _MIN_MONTH:
        base_date = datetime.date(base_year, base_month,
                                  1) - relativedelta(months=1)
        base_year = base_date.year
        base_month = base_date.month
      # otherwise, use date that is one year before the specified date
      else:
        base_year = base_year - 1
    # if specified date is a start date, base date should be later than
    # specified date
    elif prep in _START_DATE_PREPS:
      # if date is monthly, use date that is one month after the specified date
      if base_month >= _MIN_MONTH:
        base_date = datetime.date(base_year, base_month,
                                  1) + relativedelta(months=1)
        base_year = base_date.year
        base_month = base_date.month
      # otherwise, use date that is one year after the specified date
      else:
        base_year = base_year + 1
  return base_year, base_month


def get_date_range_strings(prep, year, month, year_span):
  start_date = ''
  end_date = ''
  base_year, base_month = _get_base_year_month(prep, year, month, year_span)
  year_string = str(base_year)
  month_string = _get_month_string(base_month)
  base_date = year_string + month_string
  if prep in _START_DATE_PREPS:
    start_date = base_date
    if year_span > 0:
      end_year = base_year + year_span
      end_date = str(end_year) + month_string
  elif prep in _END_DATE_PREPS:
    end_date = base_date
    if year_span > 0:
      start_year = base_year - year_span
      start_date = str(start_year) + month_string
  return start_date, end_date


def get_classification_info(classification, value):
  if classification in [
      'comparison_classification', 'correlation_classification',
      'general_classification'
  ]:
    processed_val = value.replace('(', '___')
    processed_val = processed_val.split('___')[0].strip()
    if processed_val in _CLASSIFICATION_VAL_MAPPING.get(classification, {}):
      return [_CLASSIFICATION_VAL_MAPPING[classification][processed_val]]
  elif classification in [
      'event_classification', 'ranking_classification',
      'superlative_classification', 'time_delta_classification'
  ]:
    val_list = re.findall(r"<(.*?)>", value)
    result = []
    for val in val_list:
      val_enum = val.split(':')[0]
      if val_enum in _CLASSIFICATION_VAL_MAPPING.get(classification, {}):
        result.append(_CLASSIFICATION_VAL_MAPPING[classification][val_enum])
    return result
  return []


def populate_variable_classification_columns(classifications, row, ws):
  other_classifications = []
  for classification, value in classifications.items():
    if classification == 'quantity_classification':
      val_list = re.findall(r"\((.*?)\)", value[1:len(value) - 2])
      val_string = '\n'.join(val_list)
      if not update_cell(ws, row, _CLASSIFICATION_COLUMNS[classifier]['val'],
                         val_string):
        return False
    else:
      classification_info_list = get_classification_info(classification, value)
      for c in classification_info_list:
        if c['type'] != _CLASSIFICATION_TYPE_VARIABLE:
          continue
        classifier = c['classifier']
        val = c['val']
        other_classifications.append(f'{classifier}:{val}')
  return update_cell(ws, row, _OTHER_CLASSIFICATIONS_VARIABLE_COLUMN,
                     ','.join(other_classifications))


def populate_query_classification_columns(classifications, row, ws):
  other_classifications = []
  for classification, value in classifications.items():
    if classification == 'date_classification':
      date_value = re.findall(r"Date\((.*?)\)", value)[0]
      date_value_parts = date_value.split(',')
      prep = date_value_parts[0].split('=')[-1].replace('\'', '')
      year = int(date_value_parts[1].split('=')[-1])
      month = int(date_value_parts[2].split('=')[-1])
      year_span = int(date_value_parts[3].split('=')[-1])
      start_date, end_date = get_date_range_strings(prep, year, month,
                                                    year_span)
      if not update_cell(
          ws, row, _CLASSIFICATION_COLUMNS[classification]['start'],
          start_date) or update_cell(
              ws, row, _CLASSIFICATION_COLUMNS[classification]['end'],
              end_date):
        return False
    elif classification == 'contained_in_classification':
      val_string = value.split('.')[-1]
      if not update_cell(
          ws, row, _CLASSIFICATION_COLUMNS[classification]['val'], val_string):
        return False
    else:
      classification_info_list = get_classification_info(classification, value)
      for c in classification_info_list:
        if c['type'] != _CLASSIFICATION_TYPE_QUERY:
          continue
        classifier = c['classifier']
        val = c['val']
        other_classifications.append(f'{classifier}:{val}')
  return update_cell(ws, row, _OTHER_CLASSIFICATIONS_QUERY_COLUMN,
                     ','.join(other_classifications))


def get_ordered_svs(single_svs, single_sv_scores, multi_svs):
  ordered_svs = []
  multi_sv_idx = 0
  single_sv_idx = 0
  while multi_sv_idx < len(multi_svs) and single_sv_idx < len(single_svs):
    multi_sv = multi_svs[multi_sv_idx]
    if multi_sv.get('AggCosineScore', 0) > single_sv_scores[single_sv_idx]:
      ordered_svs.append({'sv_dcid': '', 'multi_sv_info': multi_sv})
      multi_sv_idx += 1
    else:
      ordered_svs.append({
          'sv_dcid': single_svs[single_sv_idx],
          'multi_sv_info': None
      })
      single_sv_idx += 1
  while multi_sv_idx < len(multi_svs):
    multi_sv = multi_svs[multi_sv_idx]
    ordered_svs.append({'sv_dcid': '', 'multi_sv_info': multi_sv})
    multi_sv_idx += 1
  while single_sv_idx < len(single_svs):
    ordered_svs.append({
        'sv_dcid': single_svs[single_sv_idx],
        'multi_sv_info': None
    })
    single_sv_idx += 1
  return ordered_svs


def get_topic_info(topic_dcid):
  topic_info = {}
  paths = [[topic_dcid]]
  while paths:
    current_path = paths.pop()
    last_dcid = current_path[-1]
    if last_dcid != topic_dcid:
      topic_info[last_dcid] = current_path
    if last_dcid.startswith('dc/svpg'):
      starting_sv_resp = get(
          f'{NODE_API_URL}&nodes={last_dcid}&property=-%3Emember').json().get(
              'data', {}).get(last_dcid, {}).get('arcs',
                                                 {}).get('member',
                                                         {}).get('nodes', [])
    else:
      starting_sv_resp = get(
          f'{NODE_API_URL}&nodes={last_dcid}&property=-%3ErelevantVariable'
      ).json().get('data', {}).get(last_dcid,
                                   {}).get('arcs',
                                           {}).get('relevantVariable',
                                                   {}).get('nodes', [])
    for node in starting_sv_resp:
      new_path = current_path + [node.get('dcid')]
      paths.append(new_path)
  return topic_info


def get_topic_info_2(topic_dcid, level):
  topic_info = {'current': topic_dcid, 'level': level, 'children': []}
  if topic_dcid.startswith('dc/svpg'):
    starting_sv_resp = get(
        f'{NODE_API_URL}&nodes={topic_dcid}&property=-%3Emember').json().get(
            'data', {}).get(topic_dcid, {}).get('arcs',
                                                {}).get('member',
                                                        {}).get('nodes', [])
  else:
    starting_sv_resp = get(
        f'{NODE_API_URL}&nodes={topic_dcid}&property=-%3ErelevantVariable'
    ).json().get('data', {}).get(topic_dcid,
                                 {}).get('arcs',
                                         {}).get('relevantVariable',
                                                 {}).get('nodes', [])
  for node in starting_sv_resp:
    topic_info['children'].append(get_topic_info_2(node.get('dcid'), level + 1))
  return topic_info


def get_formatted_topics(ordered_svs):
  formatted_topics = {}
  topic_info_svs_dict = {}
  svs_in_topic = set()
  for sv in ordered_svs:
    sv_dcid = sv.get('sv_dcid', None)
    if not sv_dcid or not sv_dcid.startswith('dc/topic'):
      continue
    topic_info_svs = get_topic_info(sv_dcid)
    topic_info_svs_dict[sv_dcid] = topic_info_svs
    for k in topic_info_svs.keys():
      svs_in_topic.add(k)
  #topics_in_other_topics = set()
  for sv in ordered_svs:
    sv_dcid = sv.get('sv_dcid', None)
    if not sv_dcid or not sv_dcid.startswith('dc/topic'):
      continue
    if sv_dcid in svs_in_topic:
      continue
    topic_info_levels = get_topic_info_2(sv_dcid, 0)
    topic_info_svs = topic_info_svs_dict.get(sv_dcid)
    nodes_to_keep = set([sv_dcid])
    for s in ordered_svs:
      s_dcid = s.get('sv_dcid', '')
      if not s_dcid in topic_info_svs:
        continue
      svs_in_topic.add(s_dcid)
      for n in topic_info_svs.get(s_dcid):
        nodes_to_keep.add(n)
    formatted_topic = []
    next_nodes = [topic_info_levels]
    while next_nodes:
      curr_node = next_nodes.pop()
      curr_node_dcid = curr_node.get('current')
      if not curr_node_dcid in ordered_svs and not curr_node_dcid in nodes_to_keep:
        continue
      indent = ''
      for x in range(curr_node.get('level')):
        indent += '-->'
      formatted_topic.append({
          'dcids': [curr_node_dcid],
          'display': indent + curr_node_dcid
      })
      for child in curr_node.get('children'):
        next_nodes.append(child)
    formatted_topics[sv_dcid] = formatted_topic
  return formatted_topics, svs_in_topic


def get_multi_combos(idx, combos_list):
  if idx >= len(combos_list):
    return []
  combo_strings = []
  next_results = get_multi_combos(idx + 1, combos_list)
  for sv in combos_list[idx]:
    if idx == len(combos_list) - 1:
      combo_strings.append([sv])
    for result in next_results:
      curr_list = [sv]
      curr_list.extend(result)
      combo_strings.append(curr_list)
  return combo_strings


def get_formatted_sv_info(ordered_svs, opened_topics):
  formatted_topics, svs_in_topic = get_formatted_topics(ordered_svs)
  formatted_sv_info = []
  for idx, sv in enumerate(ordered_svs):
    if sv.get('sv_dcid'):
      sv_dcid = sv['sv_dcid']
      if sv_dcid in formatted_topics:
        formatted_sv_info.extend(formatted_topics[sv_dcid])
      elif sv_dcid not in svs_in_topic:
        formatted_sv_info.append({'dcids': [sv_dcid], 'display': sv_dcid})
    elif sv.get('multi_sv_info'):
      combos = []
      for idx, part in enumerate(sv['multi_sv_info'].get('Parts', [])):
        curr_list = []
        for sv_idx, sv_dcid in enumerate(part.get('SV', [])):
          if sv_idx > 1:
            break
          curr_list.append(sv_dcid)
        combos.append(curr_list)
      multi_combos = get_multi_combos(0, combos)
      for c in multi_combos:
        formatted_sv_info.append({
            'dcids': c,
            'display': 'MULTI: ' + ' && '.join(c)
        })
  return formatted_sv_info


def get_opened_topics(debug_info):
  opened_topics = {}
  for topic in debug_info.get('counters',
                              {}).get('INFO', {}).get('topics_processed', []):
    for topic_id in topic.keys():
      opened_topics[topic_id] = topic[topic_id]
  return opened_topics


def get_key_concepts(debug_info, ordered_svs):
  key_concepts_str = debug_info.get('query_with_stop_words_removal', '')
  return key_concepts_str


def get_direct_svgs(ordered_svs, opened_topics):
  added_groups = set()
  groups = []
  seen_svs = set()
  starting_svs = []
  for sv in ordered_svs:
    sv_dcid = sv.get('sv_dcid')
    if sv_dcid and not sv_dcid in seen_svs:
      starting_svs.append(sv_dcid)
      seen_svs.add(sv_dcid)
      if sv_dcid in opened_topics:
        for k, items in opened_topics[sv_dcid].items():
          if not items:
            continue
          for item in items:
            if k == 'peer_groups':
              if len(item) < 2:
                continue
              sv_list = item[1]
              for sv in sv_list:
                if not sv in seen_svs:
                  starting_svs.append(sv)
                  seen_svs.add(sv)
            else:
              if not item in seen_svs:
                starting_svs.append(item)
                seen_svs.add(item)
  nodes_param = "&".join([f'nodes={n}' for n in (starting_svs)])
  starting_sv_resp = get(
      f'{NODE_API_URL}&{nodes_param}&property=-%3EmemberOf').json().get(
          'data', {})
  for sv in starting_svs:
    svg_nodes = starting_sv_resp.get(sv, {}).get('arcs',
                                                 {}).get('memberOf',
                                                         {}).get('nodes', [])
    for svg in svg_nodes:
      svg_dcid = svg.get('dcid')
      if svg_dcid and not svg_dcid in added_groups:
        groups.append(svg_dcid)
        added_groups.add(svg_dcid)
  nodes_param = "&".join([f'nodes={n}' for n in (groups)])
  children_resp = get(
      f'{NODE_API_URL}&nodes={nodes_param}&property=%3C-specializationOf').json(
      ).get('data', {})
  groups_to_remove = set()
  for g in groups:
    to_keep = False
    for svg in children_resp.get(g, {}).get('arcs',
                                            {}).get('specializationOf',
                                                    {}).get('nodes', []):
      if not svg.get('dcid') in added_groups:
        to_keep = True
        break
    if not to_keep:
      groups_to_remove.add(g)
  return list(filter(lambda x: not x in groups_to_remove, groups))


def get_svgs(ordered_svs, opened_topics):
  added_groups = set()
  groups = []
  seen_groups = set()
  curr_groups = []
  seen_svs = set()
  starting_svs = []
  for sv in ordered_svs:
    sv_dcid = sv.get('sv_dcid')
    if sv_dcid and not sv_dcid in seen_svs:
      starting_svs.append(sv_dcid)
      seen_svs.add(sv_dcid)
      if sv_dcid in opened_topics:
        for k, items in opened_topics[sv_dcid].items():
          if not items:
            continue
          for item in items:
            if k == 'peer_groups':
              if len(item) < 2:
                continue
              sv_list = item[1]
              for sv in sv_list:
                if not sv in seen_svs:
                  starting_svs.append(sv)
                  seen_svs.add(sv)
            else:
              if not item in seen_svs:
                starting_svs.append(item)
                seen_svs.add(item)
  nodes_param = "&".join([f'nodes={n}' for n in (starting_svs)])
  starting_sv_resp = get(
      f'{NODE_API_URL}&{nodes_param}&property=-%3EmemberOf').json().get(
          'data', {})
  for sv in starting_svs:
    svg_nodes = starting_sv_resp.get(sv, {}).get('arcs',
                                                 {}).get('memberOf',
                                                         {}).get('nodes', [])
    for svg in svg_nodes:
      svg_dcid = svg.get('dcid')
      if svg_dcid and not svg_dcid in seen_groups:
        curr_groups.append(svg_dcid)
        seen_groups.add(svg_dcid)
  while len(curr_groups) > 0:
    nodes_param = "&".join([f'nodes={n}' for n in (curr_groups)])
    svg_resp = get(f'{NODE_API_URL}&{nodes_param}&property=-%3EspecializationOf'
                  ).json().get('data', {})
    next_groups = []
    for group in curr_groups:
      svg_nodes = svg_resp.get(group, {}).get('arcs',
                                              {}).get('specializationOf',
                                                      {}).get('nodes', [])
      for svg in svg_nodes:
        svg_dcid = svg.get('dcid')
        if svg_dcid == 'dc/g/Root' and not group in added_groups:
          groups.append(group)
          break
        if svg_dcid and not svg_dcid in seen_groups:
          next_groups.append(svg_dcid)
          seen_groups.add(svg_dcid)
    curr_groups = next_groups
  return groups


def get_queries(data):
  queries = []
  for idx, row in enumerate(data[1:], start=1):
    query = row[2]
    if not query:
      break
    query_type = row[1]
    queries.append({'query': query, 'type': query_type})
  return queries


def get_sentences(sv_list, sv_sentences):
  formatted_sv_sentences = []
  for sv_dcid in sv_list:
    if sv_sentences.get(sv_dcid):
      top_sv_sentence = sv_sentences[sv_dcid][0].get('sentence', '')
      formatted_sv_sentences.append(f'{sv_dcid}: {top_sv_sentence}')
  return '\n\n'.join(formatted_sv_sentences)


def update_cell(ws, row, col, val):
  time.sleep(2)
  try:
    ws.update_cell(row, col, val)
  except Exception as e:
    print(e)
    return False
  return True


def generate_results(sh):
  for ws_name in ['User queries']:
    ws = sh.worksheet(ws_name)
    data = ws.get_all_values()
    queries = get_queries(data)
    ws.clear()
    curr_row = 2
    print(f'starting {ws_name}')
    for idx, q in enumerate(queries):
      if idx >= 5:
        break
      start_row = curr_row
      query = q.get('query')
      print(query)
      query_response = requests.post(
          f'https://datacommons.org/api/explore/detect-and-fulfill?q={query}',
          json={}).json()
      debug_info = query_response.get('debug', {})
      # update place info
      place_query_info = debug_info.get('query_detection_debug_logs',
                                        {}).get('places_found_str', [])
      place_info = list(
          filter(lambda x: x != '',
                 debug_info.get('places_resolved', '').split(';')))
      # get sv info
      sv_info = debug_info.get('sv_matching', {})
      multi_svs = sv_info.get('MultiSV', {}).get('Candidates', [])
      single_svs = debug_info.get('counters',
                                  {}).get('INFO', {}).get('filtered_svs',
                                                          [[]])[0]
      opened_topics = get_opened_topics(debug_info)
      single_sv_scores = sv_info.get('CosineScore', [])
      ordered_svs = get_ordered_svs(single_svs, single_sv_scores, multi_svs)
      # get svg info
      svgs = get_svgs(ordered_svs, opened_topics)
      direct_svgs = get_direct_svgs(ordered_svs, opened_topics)
      key_concepts = get_key_concepts(debug_info, ordered_svs)
      # GET QUERY CLASSIFICATIONS
      classifications = {}
      for k in debug_info.keys():
        if not k.endswith('_classification'):
          continue
        if debug_info[k] == '<None>':
          continue
        classifications[k] = debug_info[k]

      # update cells
      update_cell_success = True
      update_cell_success &= update_cell(ws, curr_row, 2, q.get('type'))
      update_cell_success &= update_cell(
          ws, curr_row, 3,
          f'=HYPERLINK("https://datacommons.org/explore#q={query}", "{query}")')
      update_cell_success &= populate_query_classification_columns(
          classifications, curr_row, ws)
      update_cell_success &= update_cell(
          ws, curr_row, _SVG_COLUMN, ','.join(
              filter(lambda x: x is not None,
                     [_SVG_DCID_MAPPING.get(svg) for svg in svgs])))
      update_cell_success &= update_cell(ws, curr_row, _CONCEPTS_COLUMN,
                                         key_concepts)
      update_cell_success &= populate_variable_classification_columns(
          classifications, curr_row, ws)
      # UPDATE SV
      sv_sentences = debug_info.get('svs_to_sentences', {})
      formatted_sv_info = get_formatted_sv_info(ordered_svs, opened_topics)
      max_length = len(formatted_sv_info)
      for l in [len(direct_svgs), len(place_info), len(place_query_info)]:
        max_length = max(max_length, l)
      for n in range(max_length):
        if n < len(formatted_sv_info):
          info = formatted_sv_info[n]
          update_cell_success &= update_cell(ws, curr_row, _SV_COLUMN,
                                             info.get('display'))
          descriptions = get_sentences(info.get('dcids'), sv_sentences)
          update_cell_success &= update_cell(ws, curr_row, _SV_SENTENCE_COLUMN,
                                             descriptions)
          for idx, sv in enumerate(info.get('dcids')):
            update_cell_success &= update_cell(
                ws, curr_row, _SV_SENTENCE_COLUMN + idx + 1,
                f'=HYPERLINK("https://datacommons.org/browser/{sv}", "{sv}")')
        if n < len(direct_svgs):
          svg_val = direct_svgs[n]
          update_cell_success &= update_cell(
              ws, curr_row, _SVG_COLUMN_2,
              f'=HYPERLINK("https://datacommons.org/browser/{svg_val}", "{svg_val}")'
          )
        if n < len(place_info):
          update_cell_success &= update_cell(ws, curr_row, _PLACE_COLUMN,
                                             place_info[n])
        if n < len(place_query_info):
          update_cell_success &= update_cell(ws, curr_row, _PLACE_QUERY_COLUMN,
                                             place_query_info[n])
        curr_row += 1
      if not update_cell_success:
        print(f'failed for: {query}')
      if curr_row - 1 != start_row:
        try:
          cells = f'A{start_row}:C{curr_row - 1}'
          ws.merge_cells(cells, merge_type='MERGE_COLUMNS')
        except Exception as e:
          print(e)
    print(f'finished {ws_name}')


def main(_):
  gs = gspread.oauth()
  sh = gs.open_by_url(FLAGS.sheets_url)
  generate_results(sh)


if __name__ == "__main__":
  app.run(main)
