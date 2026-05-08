"""Helpers geográficos — normalização de nomes de bairro e RA."""
import re

from unidecode import unidecode

_ROMANO_PREFIXO = re.compile(r'^[IVXLCDM]+\s+', re.IGNORECASE)


def normalizar_nome_bairro(nome: str) -> str:
    """Padroniza nome de bairro/RA pra cruzar Censo, IPS e GeoJSON.

    - Remove prefixo de numeral romano usado pelo IPS ("VI LAGOA" -> "LAGOA").
    - Remove acentos via unidecode.
    - Strip + upper.
    """
    s = _ROMANO_PREFIXO.sub('', nome.strip())
    return unidecode(s).strip().upper()


if __name__ == '__main__':
    assert normalizar_nome_bairro("Lagoa") == "LAGOA"
    assert normalizar_nome_bairro("São Cristóvão") == "SAO CRISTOVAO"
    assert normalizar_nome_bairro("VI LAGOA") == "LAGOA"
    assert normalizar_nome_bairro("XXXIII REALENGO") == "REALENGO"
    assert normalizar_nome_bairro("  ii  centro  ") == "CENTRO"
    assert normalizar_nome_bairro("Ilha do Governador") == "ILHA DO GOVERNADOR"
    print("Todos os testes passaram")
