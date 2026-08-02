"""As regras do catálogo, num sítio só.

O limite de 40.000 € e os 45 dias de frescura são as duas regras que a secção 2
do AGENTS.md chama não negociáveis, e estavam definidas duas vezes cada uma —
o preço em validate_data.py e expire_campaigns.py, a idade em validate_data.py e
report_pending.py. Com os mesmos valores, por enquanto: bastava alguém mexer num
dos lados para o catálogo passar a validar por uma regra e a expirar por outra,
sem nada a assinalar a divergência.

Uma regra do projeto tem um sítio. Quem a quiser, importa-a daqui.
"""

from __future__ import annotations

# Preço máximo com IVA, para particulares, de qualquer variante publicável.
MAX_PRICE_EUR = 40_000

# A partir de quantos dias uma verificação deixa de contar como atual.
MAX_AGE_DAYS = 45
