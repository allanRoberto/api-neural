#!/usr/bin/env python3
"""
aplicar_melhorias.py

Script para aplicar automaticamente todas as melhorias do MASTER
"""

import os
import shutil
from pathlib import Path


def aplicar_melhorias():
    """Aplica todas as melhorias"""
    
    print("="*70)
    print("🚀 APLICANDO MELHORIAS DO MASTER")
    print("="*70)
    
    # Caminhos
    master_original = Path("patterns/master.py")
    master_melhorado = Path("patterns/master_melhorado.py")
    master_backup = Path("patterns/master_original_backup.py")
    
    # 1. Verificar se arquivos existem
    print("\n🔍 Verificando arquivos...")
    
    if not master_original.exists():
        print("❌ patterns/master.py não encontrado!")
        return False
    
    if not master_melhorado.exists():
        print("❌ patterns/master_melhorado.py não encontrado!")
        print("   Você precisa criar este arquivo primeiro.")
        return False
    
    print("✅ Todos os arquivos encontrados")
    
    # 2. Backup do original
    print("\n📦 Fazendo backup...")
    
    if master_backup.exists():
        print("⚠️  Backup já existe, pulando...")
    else:
        shutil.copy2(master_original, master_backup)
        print(f"✅ Backup criado: {master_backup}")
    
    # 3. Ler o master melhorado e ajustar nome da classe
    print("\n🔄 Ajustando master_melhorado.py...")
    
    with open(master_melhorado, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Substituir nome da classe
    conteudo = conteudo.replace(
        'class MasterPatternMelhorado(BasePattern):',
        'class MasterPattern(BasePattern):'
    )
    
    # 4. Sobrescrever o master.py
    print("\n💾 Substituindo master.py...")
    
    with open(master_original, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    
    print("✅ master.py substituído com sucesso!")
    
    # 5. Resumo
    print("\n" + "="*70)
    print("✅ MELHORIAS APLICADAS COM SUCESSO!")
    print("="*70)
    
    print("\n📋 Mudanças implementadas:")
    print("  ✅ Análise de múltiplas janelas (5 por padrão)")
    print("  ✅ Janela padrão = 2 (pares se repetem mais)")
    print("  ✅ min_support = 1 (mais sensível)")
    print("  ✅ Relações como multiplicadores (não aditivos)")
    print("  ✅ Fallback inteligente quando 0 padrões")
    
    print("\n📦 Arquivos:")
    print(f"  Backup:     {master_backup}")
    print(f"  Original:   {master_melhorado}")
    print(f"  Ativo:      {master_original}")
    
    print("\n🚀 Próximo passo:")
    print("  python tests/otimizador_master.py --tests 50 --save-json")
    
    print("\n💡 Para reverter:")
    print(f"  cp {master_backup} {master_original}")
    
    print()
    
    return True


if __name__ == "__main__":
    sucesso = aplicar_melhorias()
    
    if not sucesso:
        print("\n❌ Falha ao aplicar melhorias!")
        exit(1)
    
    exit(0)