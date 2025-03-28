import scrapy
import json

class FipeCrawler(scrapy.Spider):
    name = "fipe_crawler"
    
    # URLs para as APIs da tabela FIPE
    marcas_url = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
    
    def start_requests(self):
        yield scrapy.Request(url=self.marcas_url, callback=self.parse_marcas)
    
    def parse_marcas(self, response):
        marcas = json.loads(response.body)
        honda_id = None
        
        # Procura o código da Honda na lista de marcas
        for marca in marcas:
            if "honda" in marca["nome"].lower():
                honda_id = marca["codigo"]
                break
        
        if honda_id:
            # Após encontrar a Honda, busca os modelos dessa marca
            modelos_url = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{honda_id}/modelos"
            yield scrapy.Request(url=modelos_url, callback=self.parse_modelos)
    
    def parse_modelos(self, response):
        dados = json.loads(response.body)
        modelos = dados["modelos"]
        
        civic_id = None
        
        # Procura o modelo Civic na lista de modelos da Honda
        for modelo in modelos:
            if "civic" in modelo["nome"].lower():
                civic_id = modelo["codigo"]
                marca_id = response.url.split('/')[-2]
                
                # Após encontrar o Civic, busca os anos disponíveis
                anos_url = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{civic_id}/anos"
                yield scrapy.Request(url=anos_url, 
                                     callback=self.parse_anos,
                                     meta={'marca_id': marca_id, 'modelo_id': civic_id})
    
    def parse_anos(self, response):
        anos = json.loads(response.body)
        marca_id = response.meta['marca_id']
        modelo_id = response.meta['modelo_id']
        
        # Para cada ano/versão disponível, busca os detalhes do veículo
        for ano in anos:
            ano_codigo = ano["codigo"]
            detalhes_url = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_codigo}"
            yield scrapy.Request(url=detalhes_url, 
                                 callback=self.parse_detalhes)
    
    def parse_detalhes(self, response):
        detalhes = json.loads(response.body)
        
        # Extrai os detalhes do veículo, incluindo o valor FIPE
        veiculo = {
            'modelo': detalhes.get('Modelo'),
            'marca': detalhes.get('Marca'),
            'ano': detalhes.get('AnoModelo'),
            'combustivel': detalhes.get('Combustivel'),
            'codigo_fipe': detalhes.get('CodigoFipe'),
            'mes_referencia': detalhes.get('MesReferencia'),
            'valor': detalhes.get('Valor'),
            'tipo_veiculo': detalhes.get('TipoVeiculo')
        }
        
        print(veiculo)
        yield veiculo