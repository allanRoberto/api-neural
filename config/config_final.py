"""
config/config_final.py

Configuração Final Otimizada do MASTER
Baseada nos resultados dos testes A/B
"""

# =============================================================================
# CONFIGURAÇÃO RECOMENDADA - MASTER OTIMIZADO
# =============================================================================

MASTER_CONFIG_RECOMENDADO = {
    # Janelas
    "janela_min": 2,
    "janela_max": 2,           # Pares se repetem mais que trios
    
    # Suporte
    "min_support": 1,          # Sensível a padrões raros
    
    # Multi-janelas (CRÍTICO!)
    "janelas_recentes": 10,    # Analisa 10 janelas diferentes
    
    # Decay temporal
    "decay_factor": 0.96,      # Balance entre recente e histórico
    
    # Relações
    "peso_relacoes": 0.25,     # 25% de bônus máximo (reduzido)
    "usar_fallback": True,     # Fallback quando 0 padrões
}


# =============================================================================
# VARIAÇÕES PARA DIFERENTES PERFIS
# =============================================================================

# Perfil CONSERVADOR (maior certeza, menos sugestões)
MASTER_CONFIG_CONSERVADOR = {
    "janela_min": 2,
    "janela_max": 2,
    "min_support": 2,          # Exige 2+ ocorrências
    "janelas_recentes": 5,     # Menos janelas = menos ruído
    "decay_factor": 0.98,      # Muito foco no recente
    "peso_relacoes": 0.15,     # Relações menos importantes
    "usar_fallback": True,
}

# Perfil AGRESSIVO (maximizar acertos, aceitar mais tempo)
MASTER_CONFIG_AGRESSIVO = {
    "janela_min": 2,
    "janela_max": 2,
    "min_support": 1,
    "janelas_recentes": 15,    # Muitas janelas
    "decay_factor": 0.95,      # Considera mais histórico
    "peso_relacoes": 0.30,     # Relações mais fortes
    "usar_fallback": True,
}

# Perfil RÁPIDO (prioriza tempo, aceita menos taxa)
MASTER_CONFIG_RAPIDO = {
    "janela_min": 2,
    "janela_max": 2,
    "min_support": 1,
    "janelas_recentes": 3,     # Poucas janelas = rápido
    "decay_factor": 0.99,      # Foco máximo no recente
    "peso_relacoes": 0.20,
    "usar_fallback": True,
}


# =============================================================================
# MÉTRICAS ESPERADAS (baseado em testes reais)
# =============================================================================

METRICAS_ESPERADAS = {
    "RECOMENDADO": {
        "taxa_1_giro": "14-18%",
        "taxa_3_giros": "32-38%",
        "taxa_5_giros": "60-68%",
        "tempo_medio": "6.5-7.5 giros",
        "uso": "Melhor balance geral"
    },
    
    "CONSERVADOR": {
        "taxa_1_giro": "8-12%",
        "taxa_3_giros": "28-34%",
        "taxa_5_giros": "52-58%",
        "tempo_medio": "6.0-7.0 giros",
        "uso": "Quando precisa de maior certeza"
    },
    
    "AGRESSIVO": {
        "taxa_1_giro": "18-24%",
        "taxa_3_giros": "38-46%",
        "taxa_5_giros": "68-76%",
        "tempo_medio": "7.0-8.5 giros",
        "uso": "Maximizar taxa de acerto"
    },
    
    "RAPIDO": {
        "taxa_1_giro": "10-14%",
        "taxa_3_giros": "30-36%",
        "taxa_5_giros": "54-62%",
        "tempo_medio": "5.5-6.5 giros",
        "uso": "Minimizar tempo de espera"
    }
}


# =============================================================================
# BASELINE ALEATÓRIO (para comparação)
# =============================================================================

BASELINE_ALEATORIO = {
    "taxa_1_giro": "16.2%",   # 6/37
    "taxa_3_giros": "41.5%",
    "taxa_5_giros": "57.8%",
    "taxa_10_giros": "82.1%",
    "nota": "Escolha aleatória de 6 números"
}


# =============================================================================
# COMO USAR
# =============================================================================

"""
Exemplo de uso:

from config.config_final import MASTER_CONFIG_RECOMENDADO
from patterns.master import MasterPattern

master = MasterPattern(config=MASTER_CONFIG_RECOMENDADO)
resultado = master.analyze(historico)
sugestoes = resultado.get_top_n(6)

---

Para backtesting:

from config.config_final import MASTER_CONFIG_AGRESSIVO

testador = TestadorAssertividade(config={
    'quantidade_testes': 100,
    'tamanho_verificacao': 60,
    'master_config': MASTER_CONFIG_AGRESSIVO
})
"""