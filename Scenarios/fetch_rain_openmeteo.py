import requests
import os
from datetime import datetime
import sys

# Force UTF-8 encoding for stdout
sys.stdout.reconfigure(encoding='utf-8')

lat = 13.0
lon = 108.8
start_date = '2021-11-29'
end_date = '2021-12-01'

url = f'https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&hourly=precipitation&timezone=Asia%2FHo_Chi_Minh'

print('Dang tai du lieu mua tu Open-Meteo...')
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    times = data['hourly']['time']
    precipitations = data['hourly']['precipitation']
    
    output_dir = r'D:\DoAnSv\Scenarios'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'rain_Nov2021.txt')
    
    start_time = datetime.strptime(times[0], '%Y-%m-%dT%H:%M')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('# Kich ban mua (Open-Meteo ERA5) - Tu 29/11 đen 01/12/2021\n')
        f.write('# Thoi_gian(s)   Luong_mua(m/s)\n')
        
        for t_str, p in zip(times, precipitations):
            dt = datetime.strptime(t_str, '%Y-%m-%dT%H:%M')
            delta_seconds = int((dt - start_time).total_seconds())
            rain_ms = p / 3600000.0 if p > 0 else 0.0
            f.write(f'{delta_seconds:<15} {rain_ms:.10f}\n')
            
    print(f'Thanh cong! Da luu file mua vao {output_file}')
else:
    print(f'Loi API: {response.status_code}')
