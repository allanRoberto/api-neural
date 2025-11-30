// ws-sniffer.js
(function () {
    const href = window.location.href;
    const host = window.location.host || '';
    const path = window.location.pathname || '';
  
    console.log('[RB EXT] content script rodando em:', href, '| host:', host, '| path:', path);
  
    // ✅ Só a página principal da mesa:
    // https://client.pragmaticplaylive.net/desktop/classic-roulette2/
    const isMainRoulettePage =
      host === 'client.pragmaticplaylive.net' &&
      path.startsWith('/desktop/classic-roulette2'); // pode ter query no final
  
    if (!isMainRoulettePage) {
      // Não é a página raiz da mesa → não injeta o hook
      console.log('[RB EXT] não é a página principal da mesa, NÃO vou injetar injected.js aqui.');
      return;
    }
  
    console.log('[RB EXT] página principal da mesa detectada, injetando injected.js em:', href);
  
    try {
      const script = document.createElement('script');
      script.type = 'text/javascript';
      script.src = chrome.runtime.getURL('injected.js');
  
      script.onload = function () {
        console.log('[RB EXT] injected.js carregado na página da mesa:', href);
        this.remove();
      };
  
      (document.documentElement || document.head || document.body).appendChild(script);
    } catch (err) {
      console.error('[RB EXT] Falha ao injetar injected.js:', err);
    }
  })();