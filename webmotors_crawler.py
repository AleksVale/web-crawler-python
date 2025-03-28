import scrapy
import re
import json
import logging
from urllib.parse import urljoin

carros_para_buscar = json.loads("""
    [
  {"brand": "chevrolet", "model": "onix", "year": 2024, "type": "10-turbo-flex-premier-automatico", "state": "sp"},
  {"brand": "chevrolet", "model": "onix", "year": 2022, "type": "10-turbo-flex-ltz-manual", "state": "mg"},
  {"brand": "chevrolet", "model": "onix", "year": 2020, "type": "10-flex-ls-manual", "state": "rj"},
  {"brand": "chevrolet", "model": "cruze", "year": 2021, "type": "16-turbo-flex-premier-automatico", "state": "sp"},
  {"brand": "chevrolet", "model": "cruze", "year": 2019, "type": "16-flex-ltz-automatico", "state": "mg"},
  {"brand": "chevrolet", "model": "tracker", "year": 2023, "type": "12-turbo-flex-premier-automatico", "state": "rj"},
  {"brand": "volkswagen", "model": "gol", "year": 2021, "type": "10-flex-mpi-trendline-manual", "state": "sp"},
  {"brand": "volkswagen", "model": "polo", "year": 2023, "type": "10-tsi-flex-highline-automatico", "state": "mg"},
  {"brand": "volkswagen", "model": "virtus", "year": 2022, "type": "10-tsi-flex-comfortline-automatico", "state": "rj"},
  {"brand": "volkswagen", "model": "t-cross", "year": 2024, "type": "10-tsi-flex-highline-automatico", "state": "sp"},
  {"brand": "fiat", "model": "argo", "year": 2022, "type": "13-flex-drive-manual", "state": "mg"},
  {"brand": "fiat", "model": "cronos", "year": 2021, "type": "18-flex-precision-automatico", "state": "rj"},
  {"brand": "fiat", "model": "pulse", "year": 2023, "type": "10-turbo-flex-impetus-cvt", "state": "sp"},
  {"brand": "fiat", "model": "strada", "year": 2024, "type": "14-flex-volcano-cvt", "state": "mg"},
  {"brand": "toyota", "model": "corolla", "year": 2020, "type": "20-flex-altis-premium-automatico", "state": "rj"},
  {"brand": "toyota", "model": "corolla", "year": 2018, "type": "18-flex-xei-automatico", "state": "sp"},
  {"brand": "toyota", "model": "yaris", "year": 2022, "type": "15-flex-xls-automatico", "state": "mg"},
  {"brand": "hyundai", "model": "hb20", "year": 2023, "type": "10-turbo-flex-platinum-automatico", "state": "rj"},
  {"brand": "hyundai", "model": "creta", "year": 2024, "type": "20-flex-ultimate-automatico", "state": "sp"},
  {"brand": "honda", "model": "civic", "year": 2019, "type": "20-flex-touring-automatico", "state": "mg"},
  {"brand": "honda", "model": "fit", "year": 2021, "type": "15-flex-exl-automatico", "state": "rj"},
  {"brand": "honda", "model": "hr-v", "year": 2023, "type": "20-flex-advance-automatico", "state": "sp"},
  {"brand": "ford", "model": "ka", "year": 2020, "type": "10-flex-se-automatico", "state": "mg"},
  {"brand": "ford", "model": "ecosport", "year": 2019, "type": "15-flex-freestyle-automatico", "state": "rj"},
  {"brand": "ford", "model": "ranger", "year": 2024, "type": "32-diesel-limited-automatico", "state": "sp"},
  {"brand": "renault", "model": "kwid", "year": 2022, "type": "10-flex-intense-manual", "state": "mg"},
  {"brand": "renault", "model": "duster", "year": 2023, "type": "16-flex-iconic-automatico", "state": "rj"}
]
""")


class WebMotorsCrawler(scrapy.Spider):
    name = "webmotors_crawler"
    
    # URLs de base
    base_url = "https://www.webmotors.com.br/tabela-fipe/carros/"
    
    # Configurações para o crawler
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 1.5,  # Aumentado para evitar bloqueios
        'CONCURRENT_REQUESTS': 1,  # Reduzido para evitar bloqueios
        'RETRY_TIMES': 3,  # Número de tentativas em caso de falha
        'FEED_EXPORT_ENCODING': 'utf-8',
        'LOG_LEVEL': 'INFO'
    }
    
    def __init__(self, *args, **kwargs):
        super(WebMotorsCrawler, self).__init__(*args, **kwargs)
        self.processed_items = 0
        self.sucesso = 0
        self.falha = 0
        # Lista para armazenar todos os resultados
        self.resultados = []
    
    def start_requests(self):
        """Gera as requisições iniciais para cada configuração de carro"""
        self.logger.info(f"Iniciando crawler com {len(carros_para_buscar)} configurações de carros")
        
        # Itera sobre todas as configurações de carros
        for idx, config in enumerate(carros_para_buscar):
            # Constrói a URL correta para a página da tabela FIPE
            url_path = f"{config['brand']}/{config['model']}/{config['year']}/{config['type']}/{config['state'].lower()}"
            full_url = urljoin(self.base_url, url_path)
            
            self.logger.info(f"Agendando requisição {idx+1}/{len(carros_para_buscar)}: {full_url}")
            
            # Faz a requisição para a URL com a configuração como meta
            yield scrapy.Request(
                url=full_url,
                callback=self.parse_fipe_page,
                meta={'configuracao': config},
                errback=self.handle_error,
                priority=len(carros_para_buscar) - idx  # Prioridade decrescente para garantir ordem
            )
    
    def parse_fipe_page(self, response):
        """Extrai informações da página da tabela FIPE"""
        configuracao = response.meta['configuracao']
        self.processed_items += 1
        
        try:
            self.logger.info(f"Processando página: {configuracao['brand']} {configuracao['model']} {configuracao['year']} - {configuracao['state']} ({self.processed_items}/{len(carros_para_buscar)})")
            
            # Verificar se a página existe
            if response.status == 404 or "página não encontrada" in response.text.lower():
                self.logger.warning(f"Página não encontrada: {response.url}")
                self.falha += 1
                erro = {
                    'error': "Página não encontrada",
                    'url': response.url,
                    'configuracao': configuracao
                }
                self.resultados.append(erro)
                yield erro
                return
            
            # Para debug - salva o HTML da página
            if self.processed_items <= 1:  # Salva apenas a primeira página para análise
                with open('debug_response.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.logger.info(f"HTML da página salvo em debug_response.html")
            
            # Extrair marca e modelo das informações do veículo
            # Método 1: Diretamente do título da página
            title = response.css('title::text').get() or ""
            
            # Método 2: Dos elementos de breadcrumb ou título visível
            marca_element = response.css('.BreadCrumb__item a[href*="honda"]::text, .BreadCrumb__item span::text, h1::text').getall()
            marca = configuracao['brand'].upper()  # Valor padrão
            modelo = configuracao['model'].upper()  # Valor padrão
            
            # Tenta extrair marca e modelo do breadcrumb ou título
            for element in marca_element:
                element = element.strip().upper()
                if configuracao['brand'].upper() in element:
                    marca = configuracao['brand'].upper()
                if configuracao['model'].upper() in element:
                    modelo = configuracao['model'].upper()
            
            # Extração da versão (pode estar em vários elementos)
            versao_elements = response.css('.Result__info::text, .HeaderVehicle__titleVehicle::text, .HeaderVehicle__subtitle::text').getall()
            versao = None
            
            # Tenta extrair das informações de resultado
            resultado_info = response.css('.Result__info::text').get()
            if resultado_info:
                resultado_info = resultado_info.strip()
                # Extrai a versão da string com formato "VERSÃO - ANO - ESTADO"
                parts = resultado_info.split(' - ')
                if len(parts) > 0:
                    versao = parts[0].strip()
            
            # Se não encontrou a versão, tenta outros métodos
            if not versao:
                for element in versao_elements:
                    element = element.strip()
                    if len(element) > 5 and any(palavra in element.lower() for palavra in ['flex', 'gasolina', 'diesel', 'manual', 'automático', 'cvt']):
                        versao = element
                        break
            
            # Se ainda não encontrou a versão, usa o tipo da configuração como fallback
            if not versao:
                versao = configuracao['type'].replace('-', ' ').upper()
            
            # Extração dos preços usando seletores específicos
            # Primeiro tenta encontrar os preços pelos seletores de classe
            preco_elements = response.css('.Result__value::text, .Pricing__value::text, .CardPricing__price::text').getall()
            preco_fipe = None
            preco_webmotors = None
            
            # Se encontrou elementos de preço, extrai os valores
            if preco_elements:
                preco_elements = [p.strip() for p in preco_elements if p.strip()]
                if len(preco_elements) >= 1:
                    preco_fipe = preco_elements[0]
                if len(preco_elements) >= 2:
                    preco_webmotors = preco_elements[1]
            
            # Se não encontrou pelos seletores, tenta extrair via regex
            if not preco_fipe or not preco_webmotors:
                # Busca por padrões de preço no texto da página
                content = response.text
                price_pattern = r'R\$\s*([\d\.,]+)'
                price_matches = re.findall(price_pattern, content)
                
                if price_matches:
                    # Formata os preços encontrados
                    if len(price_matches) >= 1 and not preco_fipe:
                        preco_fipe = f"R$ {price_matches[0]}"
                    if len(price_matches) >= 2 and not preco_webmotors:
                        preco_webmotors = f"R$ {price_matches[1]}"
            
            # Verifica se encontrou pelo menos um preço
            if not preco_fipe and not preco_webmotors:
                self.logger.warning(f"Não foi possível encontrar preços para: {configuracao['brand']} {configuracao['model']} {configuracao['year']}")
                self.falha += 1
                erro = {
                    'error': "Preços não encontrados",
                    'url': response.url,
                    'configuracao': configuracao
                }
                self.resultados.append(erro)
                yield erro
                return
            else:
                self.sucesso += 1
            
            # Constrói o objeto com os dados extraídos
            veiculo = {
                'marca': marca,
                'modelo': modelo,
                'versao': versao,
                'ano': configuracao['year'],
                'estado': configuracao['state'].upper(),
                'preco_fipe': preco_fipe,
                'preco_webmotors': preco_webmotors,
                'url': response.url,
                'dados_configuracao': configuracao
            }
            
            self.logger.info(f"Extraído com sucesso ({self.sucesso}/{len(carros_para_buscar)}): {marca} {modelo} {configuracao['year']} - Preço FIPE: {preco_fipe}")
            self.resultados.append(veiculo)
            yield veiculo
            
        except Exception as e:
            self.logger.error(f"Erro ao processar {response.url}: {str(e)}")
            self.falha += 1
            erro = {
                'error': str(e),
                'url': response.url,
                'configuracao': configuracao
            }
            self.resultados.append(erro)
            yield erro
    
    def handle_error(self, failure):
        """Manipula erros de requisição"""
        # Extrai informações do erro
        request = failure.request
        configuracao = request.meta.get('configuracao', {})
        self.falha += 1
        
        self.logger.error(f"Falha na requisição: {request.url} - {failure.value}")
        
        erro = {
            'error': str(failure.value),
            'url': request.url,
            'configuracao': configuracao
        }
        self.resultados.append(erro)
        return erro
    
    def closed(self, reason):
        """Método executado quando o spider termina"""
        self.logger.info(f"Crawler finalizado. Razão: {reason}")
        self.logger.info(f"Total de itens processados: {self.processed_items}")
        self.logger.info(f"Sucesso: {self.sucesso}, Falha: {self.falha}")
        
        # Salva todos os resultados em um arquivo separado (backup)
        with open('todos_resultados_webmotors.json', 'w', encoding='utf-8') as f:
            json.dump(self.resultados, f, ensure_ascii=False, indent=2)
        self.logger.info(f"Todos os resultados ({len(self.resultados)}) foram salvos em 'todos_resultados_webmotors.json'")