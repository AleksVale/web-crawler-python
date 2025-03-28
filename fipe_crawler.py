import scrapy
import json
import random

class FipeCrawler(scrapy.Spider):
    name = "fipe_crawler"
    
    # URLs para as APIs da tabela FIPE
    marcas_url = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
    
    def start_requests(self):
        yield scrapy.Request(url=self.marcas_url, callback=self.parse_marcas)
    
    def parse_marcas(self, response):
        marcas = json.loads(response.body)
        
        # Agora buscamos todas as marcas
        for marca in marcas:
            marca_id = marca["codigo"]
            marca_nome = marca["nome"]
            
            # Busca os modelos para cada marca
            modelos_url = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos"
            yield scrapy.Request(
                url=modelos_url, 
                callback=self.parse_modelos,
                meta={'marca_id': marca_id, 'marca_nome': marca_nome}
            )
    
    def parse_modelos(self, response):
        dados = json.loads(response.body)
        modelos = dados["modelos"]
        marca_id = response.meta['marca_id']
        marca_nome = response.meta['marca_nome']
        
        # Seleciona até 20 modelos aleatórios (ou todos se houver menos de 20)
        modelos_limite = min(20, len(modelos))
        modelos_selecionados = random.sample(modelos, modelos_limite)
        
        for modelo in modelos_selecionados:
            modelo_id = modelo["codigo"]
            modelo_nome = modelo["nome"]
            
            # Para cada modelo, busca os anos disponíveis
            anos_url = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos"
            yield scrapy.Request(
                url=anos_url, 
                callback=self.parse_anos,
                meta={
                    'marca_id': marca_id, 
                    'marca_nome': marca_nome,
                    'modelo_id': modelo_id,
                    'modelo_nome': modelo_nome
                }
            )
    
    def parse_anos(self, response):
        anos = json.loads(response.body)
        marca_id = response.meta['marca_id']
        marca_nome = response.meta['marca_nome']
        modelo_id = response.meta['modelo_id']
        modelo_nome = response.meta['modelo_nome']
        
        # Para cada ano/versão disponível, busca os detalhes do veículo
        # Podemos limitar a um ano por modelo se quisermos reduzir o volume de requisições
        for ano in anos[:1]:  # Pegamos apenas o primeiro ano por modelo
            ano_codigo = ano["codigo"]
            detalhes_url = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_codigo}"
            yield scrapy.Request(
                url=detalhes_url, 
                callback=self.parse_detalhes,
                meta={
                    'marca_nome': marca_nome,
                    'modelo_nome': modelo_nome
                }
            )
    
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
        
        self.logger.info(f"Veículo encontrado: {veiculo['marca']} {veiculo['modelo']} - {veiculo['valor']}")
        yield veiculo
    
    # Método para iniciar o crawler com configuração para salvar em JSON
    # Você pode executar com: scrapy crawl fipe_crawler -o veiculos.json
    custom_settings = {
        'FEED_FORMAT': 'json',
        'FEED_URI': 'veiculos.json',
        'FEED_EXPORT_ENCODING': 'utf-8',
        # Adiciona delay para evitar sobrecarga na API
        'DOWNLOAD_DELAY': 0.5,
    }