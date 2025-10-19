"""
verificar_master.py

Verifica qual versão do MASTER está ativa
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from patterns.master import MasterPattern


def verificar():
    """Verifica a versão ativa"""
    
    print("\n" + "="*70)
    print("🔍 VERIFICANDO VERSÃO DO MASTER")
    print("="*70)
    
    # Criar instância
    master = MasterPattern()
    
    # Verificar atributos
    print("\n📋 Atributos encontrados:")
    
    atributos_esperados = {
        'janelas_recentes': 'Multi-janelas ativo',
        'peso_relacoes': 'Relações como multiplicadores',
        'usar_fallback': 'Fallback inteligente'
    }
    
    versao_melhorada = True
    
    for attr, descricao in atributos_esperados.items():
        tem = hasattr(master, attr)
        simbolo = "✅" if tem else "❌"
        print(f"  {simbolo} {attr:20s} → {descricao}")
        
        if not tem:
            versao_melhorada = False
    
    # Verificar métodos
    print("\n🔧 Métodos:")
    
    metodos_esperados = {
        '_buscar_padroes_exatos_offset': 'Busca com offset',
        '_aplicar_relacoes_multiplicador': 'Relações multiplicadoras',
        '_fallback_relacoes': 'Fallback'
    }
    
    for metodo, descricao in metodos_esperados.items():
        tem = hasattr(master, metodo)
        simbolo = "✅" if tem else "❌"
        print(f"  {simbolo} {metodo:35s} → {descricao}")
        
        if not tem:
            versao_melhorada = False
    
    # Conclusão
    print("\n" + "="*70)
    
    if versao_melhorada:
        print("✅ MASTER MELHORADO ESTÁ ATIVO!")
        print("="*70)
        
        # Testar valores padrão
        print("\n📊 Valores padrão:")
        print(f"  janela_min: {master.janela_min}")
        print(f"  janela_max: {master.janela_max}")
        print(f"  min_support: {master.min_support}")
        print(f"  janelas_recentes: {master.janelas_recentes}")
        print(f"  peso_relacoes: {master.peso_relacoes}")
        
        if master.janelas_recentes > 1:
            print("\n✅ Multi-janelas configurado corretamente!")
        else:
            print("\n⚠️  janelas_recentes = 1 (deveria ser 5 ou mais)")
        
    else:
        print("❌ MASTER ANTIGO AINDA ESTÁ ATIVO!")
        print("="*70)
        print("\n💡 Para ativar o MASTER melhorado:")
        print("  python aplicar_melhorias.py")
    
    print()
    
    return versao_melhorada


if __name__ == "__main__":
    versao_ok = verificar()
    exit(0 if versao_ok else 1)