"""One-off, repeatable normalization of the Portugal vehicle dataset."""

from __future__ import annotations

import json

from compile_data import ROOT, vehicle_files

VERIFIED_ON = "2026-07-21"

SOURCES = {
    "BYD Dolphin": "https://byd-auto.pt/modelos/byd-dolphin/",
    "BYD Dolphin Surf": "https://byd-auto.pt/modelos/byd-dolphin-surf/",
    "Citroën ë-C3": "https://www.citroen.pt/modelos/e-c3.html",
    "Dacia Spring": "https://www.dacia.pt/gama-hibrida-eletrica/spring-citadino.html",
    "Dongfeng Box": "https://www.dongfeng.pt/",
    "Hyundai Inster": "https://www.hyundai.pt/carros/novo-inster/",
    "Kia EV3": "https://kia.pt/modelos/kia-ev3/",
    "Leapmotor B05": "https://www.filintomota.pt/campanhas/novo-leapmotor-b05-a-partir-de-24500-euros/",
    "Leapmotor B10": "https://www.filintomota.pt/campanhas/novo-leapmotor-b10-a-partir-de-21850-euros/",
    "MG 4 Electric": "https://www.mgmotor.pt/model/mg4/",
    "Omoda E5": "https://omodajaecoo.pt/omoda/omoda-5-ev/",
    "Omoda 5 EV": "https://omodajaecoo.pt/omoda/omoda-5-ev/",
    "Peugeot E-208": "https://www.peugeot.pt/showroom/novo-peugeot-208/eletrico.html",
    "Renault 5 E-Tech": "https://www.renault.pt/veiculos-eletricos/r5-e-tech-eletrico.html",
    "Volvo EX30": "https://www.volvocars.com/pt/cars/ex30-electric/",
}

TRANSLATIONS = {
    "A-SUV/City Car": "SUV urbano do segmento A",
    "B-Hatchback": "Utilitário do segmento B",
    "City Car": "Citadino",
    "C-SUV": "SUV do segmento C",
    "Dianteira (FWD)": "Dianteira",
    "Traseira (RWD)": "Traseira",
    "All-Wheel Drive (AWD)": "Integral",
    "Torsion beam": "Eixo de torção",
    "Independent Multi-link": "Multibraços independente",
    "Multi-link": "Multibraços",
    "Ventilated Disc": "Discos ventilados",
    "Solid Disc": "Discos maciços",
    "Disc": "Discos",
    "Drum": "Tambores",
    "Manual A/C": "Ar condicionado manual",
    "Automatic A/C": "Ar condicionado automático",
    "LED headlights": "Faróis LED",
    "Rear parking sensors": "Sensores de estacionamento traseiros",
    "Reversing camera": "Câmara traseira",
    "Electric front windows": "Vidros dianteiros elétricos",
    "Speed limiter": "Limitador de velocidade",
    "Basic": "Básico",
    "Basic Infotainment": "Multimédia básico",
    "Standard Pack": "Conjunto de bateria convencional",
    "Standard Pack (lightweight)": "Conjunto de bateria convencional aligeirado",
    "Standard Pack integrated on E-GMP": "Conjunto de bateria integrado na plataforma E-GMP",
    "Cell-to-Body (CTB)": "Integração célula-carroçaria (CTB)",
    "Cell-to-Chassis (CTC)": "Integração célula-chassis (CTC)",
    "Cell-to-Pack (CTP)": "Integração célula-conjunto (CTP)",
    "Torsion beam with progressive hydraulic cushions": "Eixo de torção com batentes hidráulicos progressivos",
    "Multi-link (highly agile)": "Multibraços (elevada agilidade)",
    "Smartphone station (no central touchscreen)": "Suporte para telemóvel (sem ecrã tátil central)",
    "10.25\" color touchscreen": "Ecrã tátil a cores de 10,25\"",
    "Wireless Apple CarPlay & Android Auto": "Apple CarPlay e Android Auto sem fios",
    "Rear view camera": "Câmara traseira",
    "Rear camera & sensores de estacionamento": "Câmara traseira e sensores de estacionamento",
    "Rear sensores de estacionamento & camera": "Câmara traseira e sensores de estacionamento",
    "17\" alloy wheels": "Jantes de liga leve de 17\"",
    "18\" alloy wheels": "Jantes de liga leve de 18\"",
    "19\" aerodynamic alloy wheels": "Jantes aerodinâmicas de liga leve de 19\"",
    "Media Control (smartphone base & Bluetooth)": "Media Control (suporte para telemóvel e Bluetooth)",
    "Media Nav Live (10\" touchscreen)": "Media Nav Live (ecrã tátil de 10\")",
    "Electric mirrors & rear windows": "Retrovisores e vidros traseiros elétricos",
    "Wireless smartphone charger": "Carregador de telemóvel sem fios",
    "Wireless mobile phone charger": "Carregador de telemóvel sem fios",
    "Wireless phone charger": "Carregador de telemóvel sem fios",
    "Wireless mobile charger": "Carregador de telemóvel sem fios",
    "Wireless charger (50W, cooled)": "Carregador sem fios ventilado de 50 W",
    "Smart cruise control (NSCC)": "Controlo de velocidade inteligente (NSCC)",
    "Smart Cruise Control": "Controlo de velocidade inteligente",
    "Adaptive Cruise Control": "Controlo de velocidade adaptativo",
    "Rearview camera & parking sensors": "Câmara traseira e sensores de estacionamento",
    "Heated front seats & steering wheel": "Bancos dianteiros e volante aquecidos",
    "Heated front seats": "Bancos dianteiros aquecidos",
    "Heated & ventilated front seats": "Bancos dianteiros aquecidos e ventilados",
    "Rear spoiler double wing": "Ailerão traseiro de asa dupla",
    "LED projection headlights": "Faróis LED de projeção",
    "Slide & recline rear seats (variable trunk size)": "Bancos traseiros deslizantes e reclináveis (bagageira variável)",
    "Basic driver assistance (LKA, AEB)": "Assistência básica à condução (LKA e AEB)",
    "10.1\" OpenR Link infotainment screen with Google built-in": "Ecrã multimédia OpenR Link de 10,1\" com Google integrado",
    "Inductive smartphone charger": "Carregador de telemóvel por indução",
    "Panoramic opening roof with electric protection": "Teto panorâmico de abrir com cortina elétrica",
    "Panoramic glass roof with electric blind": "Teto panorâmico em vidro com cortina elétrica",
    "Automatic LED headlights": "Faróis LED automáticos",
    "Power adjustable front seats": "Bancos dianteiros com regulação elétrica",
    "Tinted rear windows": "Vidros traseiros escurecidos",
    "360° camera & rear parking sensors": "Câmara 360° e sensores de estacionamento traseiros",
    "Full LED headlights & rear light bar": "Faróis Full LED e faixa luminosa traseira",
    "Range Extended Electric Vehicle": "Veículo elétrico com extensor de autonomia",
    "Basic Qualcomm": "Processador Qualcomm básico",
}


def translate(value):
    if isinstance(value, dict):
        return {key: translate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [translate(item) for item in value]
    return TRANSLATIONS.get(value, value)


def find_variant(data, text):
    return next((v for v in data.get("variants", []) if text.lower() in v["name"].lower()), None)


def update_current_facts(data):
    key = f'{data["brand"]} {data["model"]}'
    if key == "Citroën ë-C3":
        you, maximum = find_variant(data, "You"), find_variant(data, "Max")
        you.update(name="You Urban Range", battery_capacity_kwh=30, wltp_range_combined_km=214,
                   power_hp=113, power_kw=83)
        you["pricing"].update(particular_list_price_vat_incl=19990,
                              particular_campaign_price_vat_incl=19990)
        maximum.update(name="Max Comfort Range", battery_capacity_kwh=44,
                       wltp_range_combined_km=322, power_hp=113, power_kw=83,
                       dc_max_kw=100, dc_charge_time_20_80_min=26)
        maximum["pricing"].update(particular_list_price_vat_incl=None,
                                  particular_campaign_price_vat_incl=None)
    elif key == "Dacia Spring":
        first = data["variants"][0]
        first.update(name="Essential electric 70", wltp_range_combined_km=225,
                     wltp_range_urban_km=315, wltp_consumption_combined_kwh_100km=12.4,
                     power_hp=70, power_kw=52)
        data["variants"] = [first]
    elif key == "Hyundai Inster":
        data["variants"][0].update(wltp_range_combined_km=320, power_hp=97, power_kw=71.1,
                                    torque_nm=147, dc_max_kw=120)
        data["variants"][1].update(wltp_range_combined_km=360, power_hp=115, power_kw=84.5,
                                    torque_nm=147, dc_max_kw=120)
    elif key == "Kia EV3":
        drive = data["variants"][0]
        drive.update(power_kw=150, torque_nm=283, acceleration_0_100_s=7.5, max_speed_kmh=170)
        drive["pricing"].update(particular_list_price_vat_incl=37990,
                                particular_campaign_price_vat_incl=36740)
        data["variants"][1].update(power_kw=150, torque_nm=283, acceleration_0_100_s=7.5,
                                    max_speed_kmh=170)
    elif key == "Leapmotor B05":
        data["variants"][-1]["wltp_range_combined_km"] = 482
    elif key == "Leapmotor B10":
        pro = data["variants"][0]
        pro["pricing"].update(company_campaign_price_vat_excl=21850,
                              company_campaign_price_vat_incl=26875.50)
        find_variant(data, "REEV")["pricing"].update(
            particular_list_price_vat_incl=None,
            particular_campaign_price_vat_incl=None,
        )
    elif key == "MG 4 Electric":
        luxury = find_variant(data, "Luxury")
        luxury.update(battery_capacity_kwh=64, wltp_range_combined_km=452, dc_max_kw=154)
        data["current_range_max_km"] = 545
    elif key in {"Omoda E5", "Omoda 5 EV"}:
        data["model"] = "5 EV"
    elif key == "Peugeot E-208":
        data["specifications"].update(battery_capacity_kwh=51, wltp_range_combined_km=433,
                                      power_hp=156, power_kw=115)
        data["charging"].update(dc_charge_time_20_80_min=27)
    elif key == "Renault 5 E-Tech":
        five, techno = data["variants"]
        five.update(wltp_range_combined_km=312, power_hp=95, power_kw=70)
        techno.update(name="Techno 120 cv autonomia urbana", battery_capacity_kwh=40,
                      wltp_range_combined_km=312, power_hp=120, power_kw=90,
                      torque_nm=225, dc_max_kw=80)
        techno["pricing"].update(particular_list_price_vat_incl=29740,
                                 particular_campaign_price_vat_incl=29740,
                                 company_campaign_price_vat_excl=None,
                                 company_campaign_price_vat_incl=None)
    elif key == "Volvo EX30":
        data["model_year"] = 2027
        data["specifications"]["wltp_range_combined_km"] = 337


def main():
    for path in vehicle_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        original_key = f'{data["brand"]} {data["model"]}'
        update_current_facts(data)
        url = SOURCES[original_key]
        data = translate(data)
        data["market"] = "PT"
        data["currency"] = "EUR"
        data["last_verified"] = VERIFIED_ON
        data["official_link"] = url
        data["availability_status"] = "não verificado" if original_key == "Dongfeng Box" else "disponível"
        data["eligible"] = data.get("release_year", 0) >= 2024 and original_key != "Dongfeng Box"
        data["eligibility_note"] = (
            "Excluído da seleção: lançamento anterior a 2024."
            if data.get("release_year", 0) < 2024 else
            "Excluído: disponibilidade do modelo no mercado português não confirmada."
            if original_key == "Dongfeng Box" else
            "Elegível para comparação no mercado português."
        )
        data["data_sources"] = [{
            "type": "página oficial PT",
            "url": url,
            "verified_on": VERIFIED_ON,
        }]
        reviews = data.get("user_reviews", {})
        reviews.update(score=None, total_reviews=0, source="Sem fonte comum verificável",
                       verification_status="não verificado")
        data["user_reviews"] = reviews
        data.get("technology_advantages", {}).pop("user_reviews", None)
        data.get("technology_advantages", {}).pop("official_link", None)
        data.get("technology_advantages", {}).pop("release_year", None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
