import scrapy
import re
import logging
import time
import random

class WebmotorsSpider(scrapy.Spider):
    name = "webmotors"
    start_urls = ["https://www.webmotors.com.br/carros/estoque"]
    
    # Configurações avançadas para evitar bloqueio
    custom_settings = {
        # Rotação de User Agents
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 2.5,  # Aumentado para reduzir detecção
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,  # Reduzido para parecer mais humano
        'LOG_LEVEL': 'INFO',
        'COOKIES_ENABLED': True,
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.google.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        },
        'RETRY_HTTP_CODES': [403, 500, 502, 503, 504, 408, 429],
        'RETRY_TIMES': 5,
    }
    
    def __init__(self, *args, **kwargs):
        super(WebmotorsSpider, self).__init__(*args, **kwargs)
        self.total_carros = 0
    
    def start_requests(self):
        """Inicializa as requisições com parâmetros adicionais"""
        for url in self.start_urls:
            # Primeiro acessa a página inicial normal
            yield scrapy.Request(
                url='https://www.webmotors.com.br/',
                callback=self.visitar_pagina_inicial,
                dont_filter=True
            )
    
    def visitar_pagina_inicial(self, response):
        """Visita a página inicial primeiro para obter cookies"""
        self.logger.info("Visitando página inicial para estabelecer sessão")
        
        # Pausa para simular comportamento de navegação humana
        time.sleep(random.uniform(1, 3))
        
        # Visita a página de estoque após obter cookies da página inicial
        yield scrapy.Request(
            url='https://www.webmotors.com.br/carros/estoque',
            callback=self.parse,
            dont_filter=True,
            meta={'cookiejar': 1}
        )

    def parse(self, response):
        """Extrai informações básicas dos carros na página"""
        # Verificar se a resposta não é um bloqueio
        if response.status == 403 or "acesso negado" in response.text.lower() or len(response.body) < 5000:
            self.logger.error("ACESSO BLOQUEADO! Tentando abordagem alternativa...")
            yield scrapy.Request(
                url='https://www.webmotors.com.br/carros/estoque?o=1',  # Tenta com parâmetro diferente
                callback=self.parse,
                dont_filter=True,
                meta={'cookiejar': 1}
            )
            return
        
        self.logger.info(f"Processando página: {response.url}")
        
        # Salvar HTML para debug
        with open('webmotors_page.html', 'w', encoding='utf-8') as f:
            f.write(response.text)

        
        
        # Selecionando todos os cards de veículos (tentando seletores alternativos)
        cards = response.css("div._Card_18bss_1, div[class*='Card_'], div.CardAd")
        
        self.logger.info(f"Encontrados {len(cards)} cards nesta página")
        
        if not cards:
            # Tenta selecionar qualquer coisa que pareça um card de carro
            self.logger.warning("Nenhum card encontrado com o seletor padrão, tentando alternativas...")
            cards = response.css("div[class*='Card'], div.card, div[data-qa*='vehicle']")
            self.logger.info(f"Encontrados {len(cards)} cards com seletor alternativo")
        
        for car in cards:
            # Obtém informações básicas
            result = self.extract_car_info(car)
            
            # Se encontrou pelo menos a marca, retorna os dados
            if result.get('marca'):
                self.total_carros += 1
                yield result
    
    def extract_car_info(self, car):
        """Extrai informações básicas de um card de carro usando principalmente atributos das imagens"""
        try:
            # Extração baseada em imagens - nova abordagem prioritária
            images = car.css('img')
            marca_modelo = None
            tipo_veiculo = None
            
            # Procura em todas as imagens por atributos úteis
            for img in images:
                title_attr = img.css('::attr(title)').get()
                alt_attr = img.css('::attr(alt)').get()
                
                # Se encontrou informações nos atributos da imagem
                if title_attr and len(title_attr.strip()) > 3:
                    marca_modelo = title_attr.strip()
                    self.logger.info(f"Informação extraída do title da imagem: {marca_modelo}")
                
                if alt_attr and len(alt_attr.strip()) > 3:
                    tipo_veiculo = alt_attr.strip()
                    self.logger.info(f"Informação extraída do alt da imagem: {tipo_veiculo}")
                
                # Se encontrou ambas informações, podemos parar
                if marca_modelo and tipo_veiculo:
                    break
            
            # Extrair marca e modelo do title ou alt da imagem
            marca, modelo = None, None
            if marca_modelo:
                marca, modelo = self.extract_marca_modelo(marca_modelo)
            
            # Busca por título caso não tenha encontrado nas imagens
            title = (
                marca_modelo or 
                car.css("h2._web-title-medium_qtpsh_51::text, h2[class*='title']::text").get() or
                ""
            ).strip()
            
            # Descrição/versão - pode usar o tipo_veiculo do alt
            descricao = (
                tipo_veiculo or
                car.css("h3._Description_70j0p_97::text, h3._body-regular-small_qtpsh_152::text, h3[class*='Description']::text").get() or
                car.css("p[class*='description']::text").get() or
                car.css("div[class*='description']::text").get() or
                ""
            ).strip()
            
            # Preço (com limpeza básica)
            preco_raw = car.css("p._body-bold-large_qtpsh_78::text, p[class*='price']::text, span[class*='price']::text").get() or ""
            preco = re.sub(r'[^\d]', '', preco_raw)
            
            # Ano (tenta extrair do texto)
            ano_text = car.css("div._CellItem_70j0p_62 p::text, p[class*='year']::text, span[class*='year']::text").get() or ""
            ano_match = re.search(r'(\d{4})', ano_text)
            ano = ano_match.group(1) if ano_match else None
            
            # Quilometragem
            km_text = car.css("div._CellItem_70j0p_62:nth-child(2) p::text, p[class*='km']::text, span[class*='km']::text").get() or ""
            km = re.sub(r'[^\d]', '', km_text) if km_text else None
            
            # Localização
            localizacao = car.css("div._BodyItem_70j0p_47 p::text, p[class*='location']::text").get() or ""
            localizacao = localizacao.strip()

            # Link do anúncio
            link = car.css("a::attr(href)").get() or ""
            if link and not link.startswith("http"):
                link = f"https://www.webmotors.com.br{link}"
            
            # Se não tiver marca/modelo da imagem, tenta do título
            if not marca and not modelo and title:
                marca, modelo = self.extract_marca_modelo(title)
            
            # Extração de imagens
            imagens = []
            # Capturar URLs de imagens com seus atributos
            for img in images:
                img_url = img.css('::attr(src)').get() or img.css('::attr(data-src)').get()
                if img_url:
                    if img_url and not img_url.endswith('.gif') and not 'placeholder' in img_url.lower():
                        # Garantir que é URL completa
                        if img_url.startswith('//'):
                            img_url = f"https:{img_url}"
                        elif not img_url.startswith(('http://', 'https://')):
                            img_url = f"https://www.webmotors.com.br{img_url}"
                        
                        # Guardar URL com metadados da imagem para referência
                        img_info = {
                            'url': img_url,
                            'title': img.css('::attr(title)').get(),
                            'alt': img.css('::attr(alt)').get()
                        }
                        
                        imagens.append(img_info)
            
            # Montagem do resultado
            return {
                "marca": marca,
                "modelo": modelo,
                "descricao": descricao,
                "preco": preco,
                "ano": ano,
                "km": km,
                "localizacao": localizacao,
                "link": link,
                "imagens": imagens,
                # Metadados originais da imagem para debug
                "image_title": marca_modelo,
                "image_alt": tipo_veiculo
            }
            
        except Exception as e:
            self.logger.error(f"Erro na extração: {e}")
            # Em caso de erro, retorna objeto vazio
            return {}
    
    def extract_marca_modelo(self, title):
        """Extrai marca e modelo do título com tratamento para casos especiais"""
        if not title:
            return None, None
            
        title = title.strip().upper()
        partes = title.split()
        
        if not partes:
            return None, None
            
        # Casos especiais de marcas compostas
        marcas_compostas = {
            "LAND": "LAND ROVER", 
            "ALFA": "ALFA ROMEO",
            "MERCEDES": "MERCEDES-BENZ",
            "GREAT": "GREAT WALL"
        }
        
        if len(partes) > 1 and partes[0] in marcas_compostas and partes[1] in ["ROVER", "ROMEO", "BENZ", "WALL"]:
            marca = f"{partes[0]} {partes[1]}"
            modelo = " ".join(partes[2:]) if len(partes) > 2 else ""
        else:
            marca = partes[0]
            modelo = " ".join(partes[1:]) if len(partes) > 1 else ""
            
        return marca, modelo
        
    def closed(self, reason):
        """Método chamado quando o spider é fechado"""
        self.logger.info(f"Spider fechado: {reason}")
        self.logger.info(f"Total de carros extraídos: {self.total_carros}")