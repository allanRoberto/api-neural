import { Router } from 'express';
import axios from 'axios';
import puppeteer from 'puppeteer'
const router = Router();

async function getWebSocketUrlWithPuppeteer(gameLink) {
    const browser = await puppeteer.launch({ 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    try {
        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
        
        const webSocketUrls = [];
        
        await page.evaluateOnNewDocument(() => {
            const originalWebSocket = window.WebSocket;
            window.WebSocket = new Proxy(originalWebSocket, {
                construct(target, args) {
                    const url = args[0];
                    console.log('WS_INTERCEPTED:', url);
                    window.__wsUrls = window.__wsUrls || [];
                    window.__wsUrls.push(url);
                    return new target(...args);
                }
            });
        });
        
        page.on('console', msg => {
            const text = msg.text();
            if (text.includes('WS_INTERCEPTED:')) {
                const url = text.split('WS_INTERCEPTED:')[1].trim();
                webSocketUrls.push(url);
            }
        });
        
        page.on('websocket', ws => {
            webSocketUrls.push(ws.url());
        });
        
        await page.goto(gameLink, { waitUntil: 'networkidle2', timeout: 60000 });
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        const capturedUrls = await page.evaluate(() => window.__wsUrls || []);
        const allUrls = [...new Set([...capturedUrls, ...webSocketUrls])];
        
        if (allUrls.length > 0) {
            const pragmaticUrl = allUrls.find(url => 
                url.includes('pragmatic') || url.includes('livecasino') || url.includes('game')
            );
            return pragmaticUrl || allUrls[0];
        }
        
        throw new Error('WebSocket URL não encontrada');
    } finally {
        await browser.close();
    }
}


// Rota de autenticação para login de usuários
router.post('/auth/login', async (req, res) => {

    try {
        // Extrai email e senha do corpo da requisição
        const { email, password } = req.body;

        // Configuração da requisição para a API da LotoGreen
        const config = {
            method: 'post',
            url: 'https://lotogreen.bet.br/api/auth/login',
            headers: { 
                'accept': 'application/json', 
                'accept-language': 'pt,pt-PT;q=0.9,en-US;q=0.8,en;q=0.7', 
                'authorization': 'Bearer null', 
                'cache-control': 'private, max-age=600', 
                'content-type': 'application/json', 
                'origin': 'https://lotogreen.bet.br', 
                'priority': 'u=1, i', 
                'referer': 'https://lotogreen.bet.br/', 
                'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"', 
                'sec-ch-ua-mobile': '?0', 
                'sec-ch-ua-platform': '"macOS"', 
                'sec-fetch-dest': 'empty', 
                'sec-fetch-mode': 'cors', 
                'sec-fetch-site': 'same-origin', 
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
            },
            data: {
                email: email,
                password: password,
                login: email
            }
        };

        // Envio da requisição de login para a API externa
        const response = await axios(config);
        

        // Configuração para verificar o status do Legitimuz (verificação de identidade)
        const legitimuzConfig = {
            method: 'get',
            url: 'https://lotogreen.bet.br/api/legitimuzStatus',
            headers: { 
                'accept': '*/*',
                'authorization': `Bearer ${response.data.access_token}`,
                'content-type': 'application/json',
                'origin': 'https://lotogreen.bet.br',
                'referer': 'https://lotogreen.bet.br/'
            }
        };

        try {
            // Consulta o status do Legitimuz com o token obtido no login
            const legitimuzResponse = await axios(legitimuzConfig);
            
            // Retorna os dados de login junto com o status do Legitimuz
            res.cookie(
                'bookmaker_token',
                response.data.access_token,
                {
                    httpOnly: true,
                    secure: false,
                    sameSite: 'lax',
                    maxAge: 1000 * 60 * 60 * 24 * 30 // 30 dias
                }
            ).json({
                isConnected: true,
                legitimuzStatus: legitimuzResponse.data
            });
        } catch (legitimuzError) {
            console.error('Erro ao verificar status do Legitimuz:', legitimuzError.message);
            
            // Retorna apenas os dados do login se houver erro no Legitimuz
            res.json({
                ...response.data,
                legitimuzStatus: null
            });
        }
    } catch (error) {
        console.log(error)
        console.error('Erro na autenticação:', error.response?.data || error.message);
        
        // Tratamento específico de erros da API
        if (error.response?.data) {
            return res.status(error.response.status).json({
                error: error.response.data.message || error.response.data
            });
        }
        
        // Retorna erro genérico caso não seja possível determinar a causa específica
        res.status(500).json({
            error: 'Erro ao realizar login. Por favor, tente novamente.'
        });
    }
});

// Endpoint para buscar dados do usuário autenticado
router.get('/auth/user', async (req, res) => {
    try {
        const accessToken = req.cookies.bookmaker_token;
        if (!accessToken) {
            return res.status(401).json({ success: false, message: 'Não autenticado na casa de apostas' });
        }
                    
        // Verifica se o token foi fornecido
        if (!accessToken) {
            return res.status(401).json({ error: 'Token não fornecido' });
        }

        // Configuração da requisição para obter dados do usuário
        const config = {
            method: 'get',
            url: 'https://lotogreen.bet.br/api/auth/me',
            headers: { 
                'accept': 'application/json',
                'authorization': `Bearer ${accessToken}`,
                'origin': 'https://lotogreen.bet.br',
                'referer': 'https://lotogreen.bet.br/'
            }
        };

        // Envio da requisição para obter dados do usuário
        const response = await axios(config);
        const userData = response.data;

        // Verifica se o MongoDB está configurado para persistir os dados do usuário
        if (User) {
            try {
                // Verifica se o usuário já existe no banco de dados
                const existingUser = await User.findOne({ 
                    $or: [
                        { email: userData.email },
                        { platformId: userData.id }
                    ]
                });

                // Se o usuário não existir, cria um novo registro
                if (!existingUser) {
                    // Criação de um novo usuário com os dados obtidos
                    const newUser = new User({
                        name: userData.name,
                        email: userData.email,
                        phone: userData.phone,
                        status: userData.status,
                        platformId: userData.id,
                        documentNumber: userData.document?.number
                    });

                    // Salva o novo usuário no banco de dados
                    await newUser.save();
                    console.log('Novo usuário salvo no MongoDB');
                }
            } catch (dbError) {
                console.error('Erro ao interagir com o banco de dados:', dbError);
                // Continua mesmo com erro no banco, já que temos os dados do usuário da API
            }
        } else {
            console.log('MongoDB não está configurado, pulando persistência do usuário');
        }

        // Retorna os dados do usuário obtidos da API
        res.json(userData);
    } catch (error) {
        console.error('Erro ao processar usuário:', error.response?.data || error.message);
        res.status(error.response?.status || 500).json({
            error: error.response?.data || 'Erro ao processar usuário'
        });
    }
});



router.get('/bookmaker/verify', async (req, res) => {
    // 1) lê o cookie
    const token = req.cookies.bookmaker_token;
  
    // 2) se não existir, já retorna false
    if (!token) {
      return res.json({ isConnected: false });
    }

    const config = {
        method: 'get',
        url: 'https://lotogreen.bet.br/api/auth/me',
        headers: { 
            'accept': 'application/json',
            'authorization': `Bearer ${token}`,
            'origin': 'https://lotogreen.bet.br',
            'referer': 'https://lotogreen.bet.br/'
        }
    };
    try {
        // Envio da requisição para obter dados do usuário
        const response = await axios(config);
        const userData = response.data;
        return res.json({
        user: userData,    
        isConnected: true 
        });
    } catch (error) {
        return res.json({ isConnected: false });
    }
  
   
  });

// Endpoint para iniciar um jogo específico
router.get('/start-game/:gameId', async (req, res) => {
    try {
        const token = req.cookies.bookmaker_token;
        if (!token) {
            return res.status(401).json({ success: false, message: 'Não autenticado na casa de apostas' });
        }
        const { gameId } = req.params;

        console.log(gameId)

        const gameResponse = await axios.get(
            `https://lotogreen.bet.br/api/casino-games/${gameId}/start?demo=0&isMobileDevice=1`,
            {
                headers: {
                    'accept': 'application/json',
                    'accept-language': 'pt',
                    'authorization': `Bearer ${token}`,
                    'content-type': 'application/json',
                    'origin': 'https://lotogreen.bet.br',
                    'referer': `https://lotogreen.bet.br/play/${gameId}`
                },
                // 👉 habilita captura de cookies
                withCredentials: true,
            }
        );

        console.log(gameResponse.data.link)

        const wsUrl = await getWebSocketUrlWithPuppeteer(gameResponse.data.link);

        // Captura cookies do header Set-Cookie (se houver)
        const setCookie = gameResponse.headers['set-cookie'];

        return res.json({
            success: true,
            link: gameResponse.data.link,
            urlGame : wsUrl,
            cookies: setCookie || [],
            message: gameResponse.data.message
        });

    } catch (error) {
        console.error('Erro ao iniciar jogo:', error.response?.data || error.message);
        return res.status(error.response?.status || 500).json({
            success: false,
            message: error.response?.data?.message || 'Erro ao iniciar jogo'
        });
    }
});




export default router;
