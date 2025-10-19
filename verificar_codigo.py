"""
verificar_codigo.py

Verifica exatamente qual código está no master.py
"""

import re
from pathlib import Path


def verificar():
    """Verifica o código"""
    
    print("\n" + "="*70)
    print("🔍 VERIFICANDO CÓDIGO DO MASTER.PY")
    print("="*70)
    
    master_path = Path("patterns/master.py")
    
    if not master_path.exists():
        print("\n❌ patterns/master.py não encontrado!")
        return
    
    with open(master_path, 'r', encoding='utf-8') as f:
        codigo = f.read()
    
    # Procurar pela função _buscar_padroes_exatos_offset
    print("\n🔍 Procurando _buscar_padroes_exatos_offset...")
    
    if '_buscar_padroes_exatos_offset' in codigo:
        print("✅ Função encontrada!")
        
        # Extrair a função
        inicio = codigo.find('def _buscar_padroes_exatos_offset')
        
        if inicio != -1:
            # Pegar os próximos 1000 caracteres
            trecho = codigo[inicio:inicio+1500]
            
            print("\n📄 Trecho da função:")
            print("─" * 70)
            
            # Mostrar só as linhas importantes
            linhas = trecho.split('\n')
            for i, linha in enumerate(linhas[:40]):
                if 'busca_inicio' in linha:
                    print(f">>> {linha}")
                elif i < 30:
                    print(f"    {linha}")
            
            print("─" * 70)
            
            # Verificar qual versão está ativa
            print("\n🔬 Análise:")
            
            if 'busca_inicio = fim + janela_size' in codigo:
                print("❌ VERSÃO ANTIGA detectada:")
                print("   busca_inicio = fim + janela_size")
                print("\n💡 Precisa aplicar correção!")
                return False
            elif 'busca_inicio = fim + 1' in codigo:
                print("✅ VERSÃO CORRIGIDA detectada:")
                print("   busca_inicio = fim + 1")
                return True
            else:
                print("⚠️  Código não reconhecido")
                return False
    else:
        print("❌ Função _buscar_padroes_exatos_offset NÃO encontrada!")
        print("   O master melhorado não foi aplicado.")
        return False


if __name__ == "__main__":
    ok = verificar()
    
    if not ok:
        print("\n" + "="*70)
        print("🔧 AÇÃO NECESSÁRIA")
        print("="*70)
        print("\n1. Execute: python aplicar_melhorias.py")
        print("2. Ou edite manualmente patterns/master.py")
        print("   Procure por: busca_inicio = fim + janela_size")
        print("   Troque por:  busca_inicio = fim + 1")
        print()
    
    exit(0 if ok else 1)