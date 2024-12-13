from flask import Flask, render_template, request, jsonify
import folium, os, json, heapq, requests
import osmnx as ox
from geopy.geocoders import Nominatim
import itertools

app = Flask(__name__)
#
#
@app.route('/api/cidades')
def get_cidades():
    file_path = os.path.join(app.root_path, 'static', 'cidades.json')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            cidades = json.load(f)
        return jsonify(cidades) 
    except Exception as e:
        return jsonify({"error": "Erro ao carregar o arquivo de cidades"}), 500

def obter_coordenadas(cidade):
    url = "https://googlelatlog.azurewebsites.net/api/http_trigger?code=_Ka380mEoqT2bUQWBiG8olL2phzfPJPpJLZGp375kLCiAzFuouiTNw%3D%3D"
    response = requests.post(url, json={"endereco": cidade})
    if response.status_code == 200:
        data = response.json()
        return data.get('Latitude'), data.get('Longitude')
    return None, None

def obter_distancia(lat1, lon1, lat2, lon2):
    url = "https://googlelatlog.azurewebsites.net/api/get_distancia?code=_Ka380mEoqT2bUQWBiG8olL2phzfPJPpJLZGp375kLCiAzFuouiTNw%3D%3D"
    payload = {
        'p1Lat': lat1,
        'p1Lng': lon1,
        'p2Lat': lat2,
        'p2Lng': lon2
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get('Distancia')
    return None

def calcular_distancia_total(cidades):
    distancia_total = 0
    distancias = []  

    for i in range(len(cidades) - 1):
        cidade1 = cidades[i]
        cidade2 = cidades[i + 1]
        
        lat1, lon1 = obter_coordenadas(cidade1)
        lat2, lon2 = obter_coordenadas(cidade2)
        
        if lat1 is not None and lon1 is not None and lat2 is not None and lon2 is not None:
            distancia = obter_distancia(lat1, lon1, lat2, lon2)
            if distancia is not None:
                distancia_total += distancia
                distancias.append(f"{cidade1} → {cidade2}: {distancia} km")
            else:
                print(f"Não foi possível calcular a distância entre {cidade1} e {cidade2}")
        else:
            print(f"Não foi possível obter as coordenadas de {cidade1} ou {cidade2}")
    
    return distancia_total, distancias

def sugerir_menor_caminho(cidades):
    menor_distancia = float('inf')
    melhor_ordem = []
    distancias_sugestao = []

    for permutacao in itertools.permutations(cidades):
        distancia_total, distancias = calcular_distancia_total(permutacao)
        if distancia_total < menor_distancia:
            menor_distancia = distancia_total
            melhor_ordem = permutacao
            distancias_sugestao = distancias

    return menor_distancia, melhor_ordem, distancias_sugestao

@app.route('/caminho', methods=['POST'])
def caminho():
    data = request.get_json()

    cidades = data['cidades']

    distancia_original, distancias_original = calcular_distancia_total(cidades)
    distancia_menor, ordem_menor, distancias_menor = sugerir_menor_caminho(cidades)

    coordenadas = {}
    for cidade in cidades:
        lat, lon = obter_coordenadas(cidade)
        if lat and lon:
            coordenadas[cidade] = [lat, lon]
    
    return jsonify({
        'distancia_original': distancia_original,
        'distancias_original': distancias_original,
        'distancia_menor': distancia_menor,
        'ordem_menor': ordem_menor,
        'distancias_menor': distancias_menor,
        'coordenadas': coordenadas
    })

@app.route('/api/obter_coordenadas', methods=['POST'])
def coordenadas():
    cidade = request.json.get('cidade')
    if cidade:
        lat, lon = obter_coordenadas(cidade)
        return jsonify({"latitude": lat, "longitude": lon}), 200
    return jsonify({"error": "Cidade não fornecida"}), 400

@app.route('/api/obter_distancia', methods=['POST'])
def distancia():
    data = request.json
    lat1, lon1 = data.get('lat1'), data.get('lon1')
    lat2, lon2 = data.get('lat2'), data.get('lon2')
    
    if None in [lat1, lon1, lat2, lon2]:
        return jsonify({"error": "Faltando coordenadas"}), 400
    
    distancia = obter_distancia(lat1, lon1, lat2, lon2)
    if distancia:
        return jsonify({"distancia": distancia}), 200
    return jsonify({"error": "Não foi possível calcular a distância"}), 500

abc_paulista = [
    "Santo André, São Paulo, Brasil",
    "São Bernardo do Campo, São Paulo, Brasil",
    "São Caetano do Sul, São Paulo, Brasil",
    "Diadema, São Paulo, Brasil"

]

graph = ox.graph_from_place(abc_paulista, network_type='drive')

print(ox.basic_stats(graph))

ox.save_graphml(graph, "abc_paulista.graphml")

@app.route('/', methods=['GET'])
def info():
    folium_map = folium.Map(location=[-23.693, -46.565], zoom_start=13)
    map_html = folium_map._repr_html_()
    print(map_html)  
    return render_template("index.html", map_html=map_html)

@app.route('/map', methods=['POST'])
def map():
    
    origem = request.form['origem']
    destino = request.form['destino']
    
    
    locator = Nominatim(user_agent="MyGeocoder")
    start_location = locator.geocode(origem)
    end_location = locator.geocode(destino)
    
    if not  end_location:
        return "Endereço de Destino não encontrado, tente novamente."
    
    if not start_location :
        return "Endereço de Origem não encontrado, tente novamente."
    
    start_coords = (start_location.latitude, start_location.longitude)  # (latitude, longitude)
    end_coords = (end_location.latitude, end_location.longitude)  # (latitude, longitude)

    orig_node = ox.distance.nearest_nodes(graph, X=start_coords[1], Y=start_coords[0])  # longitude, latitude
    dest_node = ox.distance.nearest_nodes(graph, X=end_coords[1], Y=end_coords[0])  # longitude, latitude

    route = ox.shortest_path(graph, orig_node, dest_node, weight='length')

    route_coords = [(graph.nodes[node]['y'], graph.nodes[node]['x']) for node in route]  # (latitude, longitude)

    map = folium.Map(location=start_coords, zoom_start=13)

    folium.Marker(location=start_coords, popup="Origem").add_to(map)  # (latitude, longitude)
    folium.Marker(location=end_coords, popup="Destino").add_to(map)  # (latitude, longitude)

    folium.PolyLine(locations=route_coords, color='blue', weight=5).add_to(map)

    return map._repr_html_()

geolocator = Nominatim(user_agent="myGeocoder", timeout=10)
if __name__ == '__main__':
    app.run(debug=True)