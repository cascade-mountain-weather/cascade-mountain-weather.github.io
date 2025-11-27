import requests
import re

API_TOKEN = '013a6e5128d740a7836b18c4eaaced93'
STATIONS = ['STS48', 'STS48']
RESORTS_TO_STATIONS = {
    'stevens_pass': {
        'mid': 'STB48',
        'summit': 'STS52'
    },
    'mt_baker': {
        'base': 'MTB42',
        'summit': 'MTB50'

    },
    'crystal': {
        'base': 'CMT46',
        'mid': 'CCB59',
        'summit': 'CMT69'
    },
    'paradise':{
        'base':'PVC54',
        'summit':'MU101'
    },
    'snoqualmie': {
        'base': 'ALP31',
        'mid': 'ALP44',
        'summit': 'ALP55'
    },
    'white_pass':{
        'base':'WPS45'
    },
    'blewett':{
        'base': 'BLT41'
    }
}

def synoptic_api_pull(station_id):
    url = 'https://api.synopticdata.com/v2/stations/latest'
    params = {
        'stid': station_id,
        'token': API_TOKEN
    }

    response = requests.get(url, params=params)
    data = response.json()

    observations = data['STATION'][0]['OBSERVATIONS']
    air_temp = observations.get('air_temp_value_1', dict()).get('value', None)
    snow_depth = observations.get('snow_depth_value_1', dict()).get('value', None)
    snow_interval = observations.get('snow_interval_value_1', dict()).get('value', None)

    return {'air_temp':air_temp, 'snow_depth':snow_depth, 'snow_interval':snow_interval}

RESULTS = {

}

# collect data for each resort at each elevation
for resort, stations in RESORTS_TO_STATIONS.items():
    base = stations.get('base', None)
    mid = stations.get('mid', None)
    summit = stations.get('summit', None)
    RESULTS[resort] = dict()
    if base is not None:
        RESULTS[resort]['base'] = synoptic_api_pull(base)
    if mid is not None:
        RESULTS[resort]['mid'] = synoptic_api_pull(mid)
    if summit is not None:
        RESULTS[resort]['summit'] = synoptic_api_pull(summit)

# Read the template
with open('scripts/models-tools-current-weather.tpl.html', 'r') as f:
    html = f.read()
    # Replace variables
    for area, area_data in RESULTS.items():
        for location, loc_data in area_data.items():
            for metric, value in loc_data.items():
                var_name = f'{{{{ {area}-{location}-{metric} }}}}'
                if value is None:
                    replacement = "N/A"
                elif metric == 'air_temp':
                    replacement = str(round(value * 9 / 5 + 32, 2))
                elif metric in ['snow_interval', 'snow_depth']:
                    replacement = str(round(value / 25.4, 2))
                else:
                    replacement = str(value)
                html = re.sub(re.escape(var_name), replacement, html)

    # Write the output
    with open('tools/model-tools-current-weather.html', 'w') as f:
        f.write(html)
