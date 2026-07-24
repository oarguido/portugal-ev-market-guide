import os
import json

def translate_data():
    root_dir = os.path.dirname(os.path.abspath(__file__))

    translations = {
        "byd-dolphin": {
            "pros": [
                "Excelente autonomia WLTP combinada (427 km) e urbana (559 km)",
                "Elevado desempenho (204 cv, 0-100 km/h em 7.0s)",
                "Suspensão traseira independente multi-link confortável",
                "Inclui bomba de calor de série, melhorando a eficiência no inverno"
            ],
            "cons": [
                "Preço de tabela mais elevado entre as opções originais (33.400 €)",
                "Carregamento DC máximo limitado a 110 kW"
            ]
        },
        "byd-dolphin-surf": {
            "pros": [
                "Excelente preço de proposta (€24.587 com financiamento BPI)",
                "Tamanho ultra-compacto (3.99 m), perfeito para estacionamento urbano",
                "Equipamento de segurança completo e ecrã rotativo da BYD"
            ],
            "cons": [
                "Autonomia mais curta de 322 km devido à bateria pequena (43.2 kWh)",
                "Desempenho modesto na versão Boost (0-100 km/h em 11.1s)",
                "Mala muito pequena com apenas 270 litros"
            ]
        },
        "leapmotor-b10": {
            "pros": [
                "Excelente espaço de SUV familiar com a plataforma moderna da Stellantis",
                "Arquitetura Cell-to-Chassis (CTC) que melhora a rigidez e segurança",
                "Excelente nível de equipamento tecnológico com o processador Snapdragon 8155"
            ],
            "cons": [
                "Consumo de autoestrada expectavelmente superior por ser um SUV mais alto",
                "Marca ainda em fase de afirmação no mercado europeu"
            ]
        },
        "leapmotor-b05": {
            "pros": [
                "Visual desportivo de coupé com portas sem moldura de estilo muito premium",
                "Aceleração rápida (0-100 km/h em 6.7s) e dinâmica ágil",
                "Gama de preços extremamente competitiva para o segmento C (desde 24.500 €)"
            ],
            "cons": [
                "Tejadilho descendente reduz a altura ao teto nos bancos traseiros",
                "Visibilidade traseira limitada devido ao design coupé"
            ]
        },
        "citroën-ë-c3": {
            "pros": [
                "Preço de entrada super atrativo (17.990 €) para um citadino com postura de SUV",
                "Conforto excelente com a suspensão de Batentes Hidráulicos Progressivos de série",
                "Bateria LFP muito segura e durável"
            ],
            "cons": [
                "Sem bomba de calor (PTC elétrico normal, maior perda de autonomia no inverno)",
                "Sistema de infotainment muito básico na versão You (utiliza o telemóvel)",
                "Mala média e plásticos interiores duros de baixo custo"
            ]
        },
        "renault-5-e-tech": {
            "pros": [
                "Design retro-moderno icónico e muito atraente",
                "Excelente comportamento dinâmico e suspensão traseira multi-link de série",
                "Sistema OpenR Link com Google integrado muito fluido e com planeador de rotas nativo"
            ],
            "cons": [
                "Espaço nos bancos traseiros relativamente acanhado",
                "Mala de 326 litros com plano de carga alto",
                "Versão de entrada com bateria mais pequena limitada a carregamento AC lento"
            ]
        },
        "mg-4-electric": {
            "pros": [
                "Excelente relação preço/tamanho/autonomia (segmento C familiar desde 23.900 €)",
                "Tração traseira (RWD) e distribuição de peso 50:50, muito divertido de conduzir",
                "Mala e espaço interior generosos para a categoria"
            ],
            "cons": [
                "Interface do sistema de infotainment por vezes lenta e confusa",
                "Assistência à condução (ADAS) demasiado intrusiva e com alertas sonoros irritantes",
                "Acabamentos interiores com plásticos duros em algumas áreas"
            ]
        },
        "dacia-spring": {
            "pros": [
                "O elétrico mais barato do mercado (desde 16.900 €)",
                "Excelente agilidade em cidade (comprimento curto e raio de viragem ultra-curto de 4.8 m)",
                "Consumo energético extremamente baixo"
            ],
            "cons": [
                "Autonomia limitada fora da cidade (~220 km WLTP)",
                "Baixa potência (45 cv ou 65 cv) com aceleração lenta",
                "Insonorização fraca em autoestrada e nível de segurança passiva modesto"
            ]
        },
        "dongfeng-box": {
            "pros": [
                "Preço de campanha altamente competitivo (23.500 € c/ IVA)",
                "Excelente garantia: 7 anos ou 300.000 km para o veículo, 10 anos sem limite para a bateria",
                "Equipamento topo de gama para o preço (portas sem moldura, bancos de pele ventilados, distância entre eixos de 2.66m)"
            ],
            "cons": [
                "Desempenho modesto (95 cv, 0-100 km/h em 10.6s)",
                "Mala pequena (326 litros) relativamente à largura exterior (1.81 m)",
                "Marca chinesa muito recente em Portugal (rede de assistência menos estabelecida)"
            ]
        },
        "volvo-ex30": {
            "pros": [
                "Desempenho espetacular (272 cv, 0-100 km/h em 5.7 segundos)",
                "Design escandinavo premium e excelente estatuto de marca",
                "Sistema de infotainment Google Built-in de topo"
            ],
            "cons": [
                "Preço base elevado (38.632 €) em comparação com as restantes opções",
                "Mala pequena (318 litros) e espaço muito apertado nos bancos traseiros",
                "Praticamente todos os controlos estão integrados no ecrã central (incluindo espelhos e porta-luvas)"
            ]
        },
        "hyundai-inster": {
            "pros": [
                "Design pixel-art irreverente com postura elevada de SUV urbano",
                "Habitáculo extremamente modular com bancos traseiros deslizantes e reclináveis",
                "Excelente oferta tecnológica de série com ecrã duplo de 10.25\""
            ],
            "cons": [
                "Cabine estreita (1.61m de largura), típica de um micro-carro citadino",
                "Desempenho modesto na motorização de entrada (97 cv, 0-100 km/h em 11.7s)"
            ]
        },
        "omoda-e5": {
            "pros": [
                "Equipamento de série ultra-completo na versão Comfort (Sony premium, bancos elétricos, ecrã panorâmico curvo duplo)",
                "Boa autonomia de 430 km e desempenho sólido de 204 cv",
                "Design exterior de SUV futurista com muita presença"
            ],
            "cons": [
                "Marca Chery muito recente em Portugal, rede comercial em expansão",
                "Dimensões maiores (4.40 m) que dificultam o estacionamento urbano comparado com citadinos"
            ]
        },
        "peugeot-e-208": {
            "pros": [
                "Design desportivo e assinatura visual em forma de garra muito apelativa",
                "Layout i-Cockpit 3D premium e envolvente",
                "Dinâmica de condução muito divertida e direta"
            ],
            "cons": [
                "Mala pequena de apenas 265 litros",
                "Espaço traseiro e altura ao teto limitados para adultos"
            ]
        },
        "kia-ev3": {
            "pros": [
                "Autonomia de topo na versão Long Range (605 km WLTP combinados)",
                "Carregamento bidirecional V2L de 3.6 kW para ligar eletrodomésticos",
                "Mala muito generosa de 460 litros e frunk dianteiro de 25 litros",
                "Interior minimalista espaçoso com ecrã panorâmico triplo de 30 polegadas"
            ],
            "cons": [
                "Preço elevado para particulares na versão de entrada (desde 39.500 €)",
                "Carregamento da versão Standard limitado a 102 kW"
            ]
        }
    }

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith(".json"):
                filepath = os.path.join(root, f)
                with open(filepath, "r", encoding="utf-8") as file:
                    try:
                        content = json.load(file)
                    except Exception as e:
                        print(f"Error reading {f}: {e}")
                        continue

                brand = content.get("brand", "").lower()
                model = content.get("model", "").lower()
                car_key = f"{brand}-{model}".replace(" ", "-")

                if "ë-c3" in car_key:
                    car_key = "citroën-ë-c3"
                if "peugeot" in car_key:
                    car_key = "peugeot-e-208"

                trans = translations.get(car_key)
                if trans:
                    print(f"Translating pros/cons for {content.get('brand')} {content.get('model')}")
                    content["pros"] = trans["pros"]
                    content["cons"] = trans["cons"]

                    # Also translate features list values if any are in English (basic translation)
                    if "features" in content and isinstance(content["features"], dict):
                        for trim, feat_list in content["features"].items():
                            if isinstance(feat_list, list):
                                for idx, feat in enumerate(feat_list):
                                    # Simple feature replacements
                                    feat_pt = feat.replace("Vegan leather heated seats", "Bancos aquecidos em pele vegan") \
                                                   .replace("Heated steering wheel", "Volante aquecido") \
                                                   .replace("Electric seats", "Bancos elétricos") \
                                                   .replace("rotatable touchscreen", "ecrã tátil rotativo") \
                                                   .replace("Heat pump (Bomba de calor)", "Bomba de calor") \
                                                   .replace("Heat pump", "Bomba de calor") \
                                                   .replace("360° camera", "Câmara 360°") \
                                                   .replace("Automatic A/C", "Ar Condicionado Automático") \
                                                   .replace("Manual A/C", "Ar Condicionado Manual") \
                                                   .replace("parking sensors", "sensores de estacionamento") \
                                                   .replace("Slide & recline rear seats", "Bancos traseiros deslizantes e reclináveis") \
                                                   .replace("Wireless phone charger", "Carregador de telemóvel sem fios") \
                                                   .replace("wireless charger", "carregador sem fios") \
                                                   .replace("Sony Premium Sound System", "Sistema de som premium Sony") \
                                                   .replace("Ambient lighting", "Iluminação ambiente")
                                    feat_list[idx] = feat_pt

                    with open(filepath, "w", encoding="utf-8") as file:
                        json.dump(content, file, indent=2, ensure_ascii=False)
                else:
                    print(f"No translation mapping for: {car_key}")

if __name__ == "__main__":
    translate_data()
