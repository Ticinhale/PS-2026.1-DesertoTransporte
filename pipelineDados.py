#pipeline deserto transportes
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely import wkt

'''Lendo todos os arquivos do GTFS (mesmo os que não usaremos, devem ser retirados mais tarde)'''
agency = pd.read_csv("agency.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'agency_id',
# 'agency_name', 'agency_url', 'agency_timezone', 'agency_lang', 'versao_modelo'

calendar = pd.read_csv("calendar.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'service_id',
#'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'start_date', 'end_date', 'versao_modelo'

calendarDates = pd.read_csv("calendar_dates.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'service_id',
#'DATE', 'exception_type', 'versao_modelo'

fareAttributes = pd.read_csv("fare_attributes.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'fare_id', 'price',
#'currency_type', 'payment_method', 'transfers', 'agency_id','transfer_duration', 'versao_modelo'

fareRules = pd.read_csv("fare_rules.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'fare_id',
#'route_id', 'origin_id', 'destination_id', 'contains_id','versao_modelo'

feedInfo = pd.read_csv("feed_info.csv")
#'feed_version', 'feed_start_date', 'feed_end_date','feed_publisher_name', 'feed_publisher_url', 'feed_lang',
#'default_lang', 'feed_contact_email', 'feed_contact_url','feed_update_datetime', 'versao_modelo'

frequencies = pd.read_csv("frequencies.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'trip_id', 
# 'start_time', 'end_time', 'headway_secs', 'exact_times','versao_modelo'

ordemServico = pd.read_csv("ordem_servico.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'tipo_os', 'servico', 
# 'vista', 'consorcio', 'horario_inicio', 'horario_fim', 'extensao_ida', 'extensao_volta', 'partidas_ida', 'partidas_volta',
#'viagens_planejadas', 'distancia_total_planejada', 'tipo_dia', 'versao_modelo'

ordemServicoAlt = pd.read_csv("ordem_servico_trajeto_alternativo.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'tipo_os', 'servico', 'consorcio', 'vista', 'ativacao', 'descricao', 'evento',
#'extensao_ida', 'extensao_volta', 'inicio_periodo', 'fim_periodo','versao_modelo'

shapesGeom = pd.read_csv("shapes_geom.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'shape_id', 'shape',
#'shape_distance', 'start_pt', 'end_pt', 'versao_modelo'

routes = pd.read_csv("routes.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'route_id','agency_id', 
#'route_short_name', 'route_long_name', 'route_desc','route_type', 'route_url', 'route_color', 'route_text_color',
#'route_sort_order', 'continuous_pickup', 'continuous_drop_off','network_id', 'versao_modelo'

stops = pd.read_csv("stops.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'stop_id','stop_code', 'stop_name', 'tts_stop_name', 'stop_desc', 'stop_lat',
#'stop_lon', 'zone_id', 'stop_url', 'location_type', 'parent_station','stop_timezone', 
# 'wheelchair_boarding', 'level_id', 'platform_code', 'versao_modelo'

paradas = pd.read_csv("paradas.csv")
#'X', 'Y', 'fid', 'wheelchair_boarding', 'zone_id', 'platform_code','stop_id', 
# 'stop_code', 'stop_url', 'stop_desc', 'stop_timezone','stop_name', 'location_type', 'parent_station'

trips = pd.read_csv("trips.csv")
#'feed_version', 'feed_start_date', 'feed_end_date', 'route_id','service_id', 'trip_id', 'trip_headsign', 'trip_short_name',
#'direction_id', 'block_id', 'shape_id', 'wheelchair_accessible','bikes_allowed', 'versao_modelo'

# Após cada read_csv dos arquivos que vão ser usados:
stops = stops.sort_values('feed_start_date').drop_duplicates(subset='stop_id', keep='last')
routes = routes.sort_values('feed_start_date').drop_duplicates(subset='route_id', keep='last')
shapesGeom = shapesGeom.sort_values('feed_start_date').drop_duplicates(subset='shape_id', keep='last')

# trips precisa do par (route_id, shape_id) único, não trip_id
# (porque trips tem milhões de execuções planejadas)
trips_unicos = trips[['route_id', 'shape_id', 'trip_id']].drop_duplicates()

# algumas paradas estão com coordenadas vazias
stops = stops.dropna(subset=['stop_lat', 'stop_lon'])

'''Tirando colunas desnecessárias dos dados de interesse'''
routes = routes.drop(columns=['feed_version', 'feed_start_date', 
                              'feed_end_date', 'agency_id', 'route_url', 'route_color', 'route_text_color','network_id', 'versao_modelo',
                              'route_sort_order', 'continuous_pickup', 'continuous_drop_off'])


trips = trips.drop(columns=['feed_version', 'feed_start_date', 'feed_end_date',
                            'service_id','block_id', 'wheelchair_accessible','bikes_allowed', 'versao_modelo'])


stops = stops.drop(columns=['feed_version', 'feed_start_date', 'feed_end_date', 'wheelchair_boarding', 'stop_code',
                            'level_id', 'platform_code', 'versao_modelo', 'stop_timezone','tts_stop_name', 'stop_desc', 
                            'zone_id', 'stop_url', 'location_type', 'parent_station'])

shapesGeom = shapesGeom.drop(columns=['feed_version', 'feed_start_date', 'feed_end_date', 'versao_modelo'])

#Após retirar, cada um desses dataframes têm as seguintes colunas:
#trips: route_id, trip_id, trip_headsign, trip_short_name, direction_id, shape_id
#routes: route_id, route_short_name, route_long_name, route_desc, route_type
#stops: stop_id, stop_name, stop_lat, stop_lon
#shapesGeom: shape_id, shape, shape_distance, start_pt, end_pt

def quantidadeDeViagensPorRota():
    '''Conta quantas viagens são feitas por rota. Cria um dataframe (viagensRota) que possui como colunas: id da rota("route_id"), 
    quantidade de viagens("count") e nome da rota("route_long_name).'''
    quantidades = trips_unicos["route_id"].value_counts().reset_index()
    viagensRota = quantidades.merge(routes[['route_id', 'route_long_name']], on='route_id', how='left')
    return viagensRota
     


def pegarTodasParadas(buffer_metros=30):
    '''
    Para cada shape, listar todas as paradas próximas (dentro de `buffer_metros`).
    
    Substitui o for por join vetorizado (geopandas).
    Reprojeta para trabalhar em metros, o valor de 30m é a tolerância padrão da literatura de transporte público, suficiente para capturar a diferença 
    entre o eixo da via (onde o shape é desenhado) e a calçada (onde fica a parada).
    '''
    # 1. Converter shapes para GeoDataFrame
    shapes_df = shapesGeom.copy()
    shapes_df['geometry'] = shapes_df['shape'].apply(
        lambda s: wkt.loads(s) if pd.notna(s) else None
    )
    shapes_df = shapes_df.dropna(subset=['geometry'])
    shapes_gdf = gpd.GeoDataFrame(shapes_df, geometry='geometry', crs='EPSG:4326')
    
    # 2. Converter stops para GeoDataFrame de pontos
    stops_gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops['stop_lon'], stops['stop_lat']),
        crs='EPSG:4326'
    )
    
    # 3. Reprojetar para EPSG:31983 (UTM 23S, métrico — padrão IBGE pro Rio)
    shapes_metric = shapes_gdf.to_crs('EPSG:31983')
    stops_metric = stops_gdf.to_crs('EPSG:31983')
    
    # 4. Buffer em metros ao redor de cada shape
    shapes_metric['geometry'] = shapes_metric.geometry.buffer(buffer_metros)
    
    # 5. Spatial join — uma operação, vetorizada
    paradas_por_shape = gpd.sjoin(
        stops_metric[['stop_id', 'geometry']],
        shapes_metric[['shape_id', 'geometry']],
        how='inner',
        predicate='within'
    )
    
    # 6. Agrupar para retornar uma lista de paradas por shape
    resultado = (paradas_por_shape
                 .groupby('shape_id')['stop_id']
                 .apply(list)
                 .reset_index()
                 .rename(columns={'stop_id': 'paradas'}))
    
    return resultado

viagensRota = quantidadeDeViagensPorRota()
#print(viagensRota)

#pegarTodasParadas()

if __name__ == '__main__':
    print('=== Quantidade de viagens por rota ===')
    viagensRota = quantidadeDeViagensPorRota()
    print(viagensRota.head(10))
    
    print('\n=== Inferindo paradas por shape (buffer 30m) ===')
    paradas_por_shape = pegarTodasParadas(buffer_metros=30)
    
    # Sanity check
    n_paradas = paradas_por_shape['paradas'].apply(len)
    print(f'Shapes com paradas: {len(paradas_por_shape):,}')
    print(f'Mediana de paradas por shape: {n_paradas.median():.0f}')
    print(f'Min/Max: {n_paradas.min()} / {n_paradas.max()}')
    
    # Salvar
    paradas_por_shape.to_parquet('paradas_por_shape.parquet')
    print('\n✓ Salvo: paradas_por_shape.parquet')


    



