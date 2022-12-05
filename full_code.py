import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import date
import seaborn as sns
import matplotlib.pyplot as plt
import geopandas
import matplotlib.patches as mpatches

#get cities and states list

def get_cities():
    page = requests.get('https://en.wikipedia.org/wiki/List_of_Nigerian_cities_by_population')
    print(page.status_code)

    soup = BeautifulSoup(page.text, 'lxml')

    table_content = soup.find('table',class_='wikitable sortable')

    col = []
    for header in table_content.find_all('th'):
        col.append(header.text)

    all_data = []
    for table_row in table_content.find_all('tr'):
        cont = table_row.find_all('td')
        data = []
        for i in cont:
            data.append(i.text.split('\n')[0])
        all_data.append(data)

    column = []
    for a in col:
        column.append(a.split('\n')[0])
    df = pd.DataFrame(all_data, columns=column)
    return df
states_df = get_cities()
#The city names contains some characters that are not needed
city_list = []
for i in states_df['City']:
    city_name = str(i).split('[')[0]
    city_list.append(city_name)

states_df['City_name'] = city_list
#drop the initial city table 
states_df.drop('City', axis=1, inplace=True)

#save the data 
states_df.to_csv('states.csv')

#now get the weather details

def get_weather():
    header = {
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36'
    }


    col_list = [
        'city_name',
        'Weather Status',
        'Temperature',
        'Precipitation',
        'Humidity',
        'Wind'
    ]


    row_data = []

    for city in states_df[states_df['City_name'].notnull()]['City_name']:
        #print(city)
        try:
            url = f'https://www.google.com/search?q=weather+{city}'
            response = requests.get(url, headers = header)
            print('............connecting.................')
            #print(response.status_code)
            soup = BeautifulSoup(response.text,'html.parser')
            city_name = soup.find('div',attrs={'id':"wob_loc"}).text
            status = soup.find('img',id='wob_tci').attrs['alt']
            temp = soup.find('span',id='wob_tm').text
            more_details = soup.find('div',class_='wtsRwe').text.split('%')
            prep = more_details[0] + '%'
            humidity = more_details[1] + '%'
            wind = more_details[2]
            row_data.append([city_name,status,temp,prep,humidity,wind])
            print(f'Added {city_name} weather details to row data')
        except:
            pass
        #avoid 409 error
        time.sleep(5)
    weather_df = pd.DataFrame(row_data,columns=col_list)
    return weather_df

weather_data = get_weather()
#save data
weather_data.to_csv('weather.csv')
#merge the two dataframes using the city field as primary key
weather_and_state = pd.merge(
    states_df,
    weather_data,
    how='inner',
    left_on = 'City_name',
    right_on = 'city_name'
)

#load the geojson file that contains nigeria states boundaries

gdf = geopandas.read_file('Niger_geojson.geojson')
from_gdf = gdf[['admin1Name','geometry']]
#rename a column
from_gdf_renamed = from_gdf.rename(columns={'admin1Name':'State'})

#merge the weather and states dataframe with the geojson data

merged_df = from_gdf_renamed.set_index('State').join(weather_and_state.set_index('State'))
merged_df['Weather Status'].fillna('Undetermined', inplace=True)

#set a color for each unique weather status using seaborn color palette
status_list = list(set(merged_df['Weather Status']))
status_pal = list(sns.color_palette(palette='Spectral',
                             n_colors=len(status_list)).as_hex())
#Make a dictionary with weather status as key and the palette as calue
dict_color = dict(zip(status_list, status_pal))
#get color for each weather status
color_list = [dict_color.get(i) for i in merged_df['Weather Status']]

#initiate matplotlib figure 
fig = plt.figure()

ax = fig.add_axes([0,0,1,1])
data_plot = merged_df.plot(column='Weather Status', ax=ax, color=color_list, linewidth = 0.8, edgecolor='0.8')
#turm the axes off
ax.axis('off')

#create the legends and set positions
list_status = list(merged_df['Weather Status'].unique())
legends = [mpatches.Patch(color=dict_color.get(i),
                          label=i) for i in list_status]
plt.legend(handles=legends, bbox_to_anchor=(1.5, 1.01), title='Weather Status')
most_appeared = merged_df['Weather Status'].value_counts().nlargest(1).index[0]
len_most_appeared = merged_df['Weather Status'].value_counts().nlargest(1).values[0]
room_temp = [i for i in range(26,28)]
merged_df['Temperature'].fillna(0.0,inplace=True)
merged_df['Temperature'] = merged_df['Temperature'].astype('int')
#print(list(merged_df['Temperature']))
less_room_temp = merged_df[merged_df['Temperature']<26]
higher_room_temp = merged_df[merged_df['Temperature']>28]
#print(len(btwn_room_temp))
wind_speed = []
for value in merged_df['Wind']:
    try:
        v = value.split(': ')
        wind_speed.append(int(v[1].split('km/')[0]))
    except:
        wind_speed.append(0)
    #print(value)
merged_df['wind_speed'] = wind_speed

prec_list = []
for value in merged_df['Precipitation']:
    try:
        v = value.split(':')
        prec_list.append(int(v[1].split('%')[0]))
    except:
        prec_list.append(0)
merged_df['prec'] = prec_list

humidity = []
for value in merged_df['Humidity']:
    try:
        v = value.split(':')
        humidity.append(int(v[1].split('%')[0]))
    except:
        humidity.append(0)
merged_df['humidity_rate'] = humidity

normal_wind = merged_df[merged_df['wind_speed'] <= 20]
average_prep = merged_df['prec'].mean()
average_humidity = merged_df['humidity_rate'].mean()
plt.gcf().text(0.002, 1.30, f'Weather report in various cities in Nigeria as of {date.today()}', fontsize=14)
plt.gcf().text(0.002, 1.25, 'The data is scraped from google and these insights are made:', fontsize=10)
plt.gcf().text(0.002,1.20,f'{most_appeared} has most occurences with {len_most_appeared} cities in total', fontsize=9)
plt.gcf().text(0.002,1.15,f'{len(higher_room_temp)} cities has temperature higher than room temperature and {len(less_room_temp)} has lower',fontsize=9)
plt.gcf().text(0.002,1.10,f'{len(normal_wind)} cities experiences a normal wind speed of less than 20km/h',fontsize=9)
plt.gcf().text(0.002,1.05,f'The average humidity is {average_humidity:.2f}%',fontsize=9)
plt.gcf().text(0.002,1.00,f'The average precipitation is {average_prep:.2f}% ',fontsize=9)
plt.figtext(1.15,0.01,'Made by Enoch',fontsize=12)
plt.savefig('figure.png', bbox_inches='tight')
print('Figure Saved')
