// injected.js
// Roda DENTRO da página da Pragmatic (client.pragmaticplaylive.net)
// Este arquivo deve ser injetado apenas na URL:
//   https://client.pragmaticplaylive.net/desktop/classic-roulette2/...

(function () {
    try {
      console.log(
        '[RevesBot WS] Hook de WebSocket: começando injeção...',
        window.location.href
      );
  
      const OriginalWebSocket = window.WebSocket;
      if (!OriginalWebSocket) {
        console.warn('[RevesBot WS] window.WebSocket não encontrado.');
        return;
      }
  
      // Estado LOCAL deste frame (classic-roulette2)
      let lastSocket = null;
      let lastGameInfo = null;
  
      // Origem do painel RevesBot (onde está o botão "executar aposta")
      const PANEL_ORIGIN = 'https://ia.revesbot.com.br';
  
      // ============================
      // PARSE DO XML <betsopen ...>
      // ============================
      function parseBetsOpenMessage(xmlMessage) {
        try {
          if (typeof xmlMessage !== 'string') return null;
  
          const gameMatch = xmlMessage.match(/game="([^"]+)"/);
          const tableMatch = xmlMessage.match(/table="([^"]+)"/);
  
          if (gameMatch && tableMatch) {
            const info = { game: gameMatch[1], table: tableMatch[1] };
            console.log(
              '[RevesBot WS] gameInfo capturado NESTE FRAME:',
              info,
              'href:',
              window.location.href
            );
            return info;
          }
          return null;
        } catch (err) {
          console.error('[RevesBot WS] Erro ao parsear betsopen:', err);
          return null;
        }
      }
  
      // Mesmo conceito de checksum/timestamp usado no bot.js
      function generateChecksumTimestamp() {
        return Date.now().toString();
      }
  
      // Monta o XML de aposta com base em game/table + números
      function buildBetMessage(gameInfo, numbers, valorAposta) {
        const checksum = generateChecksumTimestamp();
  
        const betsXML = numbers
          .map((n) => {
            const num = Number(n);
            // Mesma regra do bot.js:
            //  - 0 -> bc = 2
            //  - demais -> bc = n + 3
            const betCode = num === 0 ? 2 : num + 3;
            return `<bet amt="${valorAposta}" bc="${betCode}" ck="${checksum}" />`;
          })
          .join('');
  
        const message =
          `<command channel="table-${gameInfo.table}" >` +
          `<lpbet gm="roulette_desktop" gId="${gameInfo.game}" uId="ppc1735139140386" ck="${checksum}">` +
          betsXML +
          `</lpbet></command>`;
  
        return message;
      }
  
      // ============================
      // WRAP DO WebSocket LOCAL
      // ============================
      function RBWebSocket(url, protocols) {
        const socket =
          protocols !== undefined
            ? new OriginalWebSocket(url, protocols)
            : new OriginalWebSocket(url);
  
        lastSocket = socket;
  
        try {
          const wsUrl = socket.url || url;
          console.log(
            '[RevesBot WS] WebSocket criado NESTE FRAME:',
            wsUrl,
            'href:',
            window.location.href
          );
  
          socket.addEventListener('open', () => {
            console.log(
              '[RevesBot WS] WebSocket ABERTO NESTE FRAME:',
              wsUrl,
              'href:',
              window.location.href
            );
          });
  
          socket.addEventListener('close', () => {
            console.log(
              '[RevesBot WS] WebSocket FECHADO NESTE FRAME:',
              wsUrl,
              'href:',
              window.location.href
            );
          });
        } catch (e) {
          console.error(
            '[RevesBot WS] Erro ao registrar URL do WebSocket',
            e
          );
        }
  
        // Observa mensagens da mesa pra capturar game/table
        socket.addEventListener('message', (event) => {
          try {
            const data = event.data;
            if (typeof data !== 'string') return;
  
            if (data.includes('<betsopen') || data.includes('<betsclosingsoon')) {
              const info = parseBetsOpenMessage(data);
              if (info) {
                lastGameInfo = info;
              }
            }
          } catch (err) {
            console.error('[RevesBot WS] Erro ao inspecionar mensagem WS:', err);
          }
        });
  
        return socket;
      }
  
      // Copia prototype e constantes do WebSocket original
      RBWebSocket.prototype = OriginalWebSocket.prototype;
      ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'].forEach((key) => {
        if (key in OriginalWebSocket) {
          RBWebSocket[key] = OriginalWebSocket[key];
        }
      });
  
      // Substitui WebSocket global NESTE FRAME (classic-roulette2)
      window.WebSocket = RBWebSocket;
  
      // ============================
      // FUNÇÃO QUE TENTA APOSTAR NESTE FRAME
      // ============================
      function handlePlaceBet(payload) {
        try {
          if (!payload || typeof payload !== 'object') {
            console.warn(
              '[RevesBot WS] handlePlaceBet chamado com payload inválido NESTE FRAME:',
              payload,
              'href:',
              window.location.href
            );
            return;
          }
  
          // Aceita tanto:
          //  - { action: 'place_bet', origin: 'revesbot_frontend', numbers: [...] }
          //  - quanto { type: 'RB_PLACE_BET', payload: { numbers: [...] } }
          const numbers =
            Array.isArray(payload.numbers)
              ? payload.numbers
              : Array.isArray(payload.payload?.numbers)
                ? payload.payload.numbers
                : [];
  
          if (!numbers.length) {
            console.warn(
              '[RevesBot WS] RB_PLACE_BET sem números para apostar NESTE FRAME. href:',
              window.location.href
            );
            return;
          }
  
          // Valor da aposta (em centavos). Pode vir do payload; se não vier, usa 50 pra teste.
          const valorAposta =
            typeof payload.amount === 'number'
              ? payload.amount
              : typeof payload.payload?.amount === 'number'
                ? payload.payload.amount
                : 50;
  
          const socket = lastSocket;
          const gameInfo = lastGameInfo;
  
          console.log('[RevesBot WS] Estado na hora da aposta NESTE FRAME:', {
            href: window.location.href,
            hasSocket: !!socket,
            socketReadyState: socket && socket.readyState,
            gameInfo
          });
  
          if (!socket || socket.readyState !== OriginalWebSocket.OPEN) {
            console.warn(
              '[RevesBot WS] Nenhum WebSocket ABERTO NESTE FRAME para enviar aposta. href:',
              window.location.href
            );
            return;
          }
  
          if (!gameInfo) {
            console.warn(
              '[RevesBot WS] gameInfo ainda não capturado NESTE FRAME. Aguardando <betsopen>. href:',
              window.location.href
            );
            return;
          }
  
          const message = buildBetMessage(gameInfo, numbers, valorAposta);
  
          console.log(
            '[RevesBot WS] Enviando aposta pelo WebSocket NESTE FRAME:',
            {
              href: window.location.href,
              numbers,
              valorAposta,
              gameInfo,
              xml: message
            }
          );
  
          socket.send(message);
        } catch (err) {
          console.error(
            '[RevesBot WS] Erro em handlePlaceBet NESTE FRAME:',
            err,
            'href:',
            window.location.href
          );
        }
      }
  
      // ============================
      // RECEBE COMANDOS DO FRONTEND
      // ============================
      window.addEventListener('message', function (event) {
        try {
          const data = event.data;
          if (!data || typeof data !== 'object') return;
  
          // 1) Mensagem vinda do painel (ia.revesbot.com.br)
          const isFromPanel =
            event.origin === PANEL_ORIGIN &&
            data.action === 'place_bet' &&
            data.origin === 'revesbot_frontend';
  
          // 2) Opcional: formato alternativo com type RB_PLACE_BET
          const isFromPanelAlt =
            event.origin === PANEL_ORIGIN &&
            data.type === 'RB_PLACE_BET';
  
          if (!isFromPanel && !isFromPanelAlt) {
            return;
          }
  
          console.log(
            '[RevesBot WS] Mensagem de aposta RECEBIDA do painel NESTE FRAME. href:',
            window.location.href,
            'data:',
            data
          );
  
          const payload = isFromPanel ? data : data.payload || data;
          handlePlaceBet(payload);
        } catch (err) {
          console.error(
            '[RevesBot WS] Erro ao processar postMessage NESTE FRAME:',
            err,
            'href:',
            window.location.href
          );
        }
      });
  
      console.log(
        '[RevesBot WS] Hook de WebSocket instalado NESTE FRAME:',
        window.location.href
      );
    } catch (err) {
      console.error(
        '[RevesBot WS] Erro geral no injected.js:',
        err,
        'href:',
        window.location.href
      );
    }
  })();