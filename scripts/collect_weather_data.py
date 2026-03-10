import requests
import re

API_TOKEN = '013a6e5128d740a7836b18c4eaaced93'
STATIONS = ['STS48', 'STS48']
RESORTS_TO_STATIONS = {
    'stevens_pass': {
        'mid': 'STB48',
        'summit': 'STS52',
        'tye': 'STS54'
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
        'base':'WPS45',
        'pigtail':'WPS60'
    },
    'blewett':{
        'base': 'BLT41'
    },
    'berne':{
        'base': 'BRN27'
    },
    'waterhole':{
        'base': 'WHSW1'
    },
    'harts_pass':{
        'base': 'HRPW1'
    },
    'easy_pass':{
        'base': 'EPSW1'
    },
    'swift_creek':{
        'base': 'SWCW1'
    },
    'lyman_lake':{
        'base': 'LYLW1'
    },
    'wells_creek':{
        'base': 'WCSW1'
    },
    'olallie_meadows':{
        'base': 'OMWW1'
    },
    'stampede_pass':{
        'base': 'SMPW1'
    },
    'fish_lake':{
        'base': 'FISW1'
    },
    'sasse_ridge':{
        'base': 'SASW1'
    },
    'mf_nooksack':{
        'base': 'MNOW1'
    },
    'mt_crag':{
        'base': 'MTCW1'
    },
    'dungeness':{
        'base': 'DGSW1'
    },
    'corral_pass':{
        'base': 'COPW1'
    },
    'grouse_camp':{
        'base': 'GRCW1'
    },
    'june_lake':{
        'base': 'MRBW1'
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

# Add Washington Pass stations
RESORTS_TO_STATIONS['washington_pass'] = {
    'base': 'WAP55',   # 48.53/-120.66 @ 5450 ft
    'upper': 'WAP67'   # 48.53/-120.65 @ 6680 ft
}

# collect data for each resort at each elevation (support arbitrary keys like base/mid/summit/upper)
for resort, stations in RESORTS_TO_STATIONS.items():
    RESULTS[resort] = dict()
    for level, station_id in stations.items():
        if station_id:
            RESULTS[resort][level] = synoptic_api_pull(station_id)

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
