/**
 * TravelSales.ai / AI Studio - Universal Embeddable Chatbot Widget
 * Soporte Multi-Diseño: Circular, Pill, Modo Claro/Oscuro/Glass, Posición Libre y Auto-Adaptable
 * <script src="/widget.js" data-tenant="MI-NEGOCIO"></script>
 */

(function () {
    const currentScript = document.currentScript || document.querySelector('script[src*="widget.js"]');
    const tenantId = (currentScript && currentScript.getAttribute('data-tenant')) || 'KLYVEN-STUDIO';
    const forceAutoTheme = currentScript && currentScript.getAttribute('data-auto-theme') === 'true';

    let apiBase = window.location.origin;
    if (currentScript && currentScript.src) {
        try {
            apiBase = new URL(currentScript.src).origin;
        } catch(e) {
            apiBase = window.location.origin;
        }
    }

    let conversationHistory = [];

    function detectHostPageColor() {
        try {
            const metaTheme = document.querySelector('meta[name="theme-color"]');
            if (metaTheme && metaTheme.content) return metaTheme.content;
            const nav = document.querySelector('header, nav');
            if (nav) {
                const bg = window.getComputedStyle(nav).backgroundColor;
                if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
            }
            const primaryVar = window.getComputedStyle(document.documentElement).getPropertyValue('--primary').trim();
            if (primaryVar) return primaryVar;
        } catch(e) {}
        return null;
    }

    function initWidget() {
        if (document.getElementById('travelsales-bubble')) return;

        // Estilos base
        const style = document.createElement('style');
        style.id = 'ts-widget-styles';
        style.innerHTML = `
            #travelsales-bubble {
                position: fixed !important;
                bottom: 24px !important;
                right: 24px !important;
                background: linear-gradient(135deg, #0f172a, #2563eb);
                border-radius: 50px !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35) !important;
                cursor: pointer !important;
                z-index: 2147483647 !important;
                transition: transform 0.2s ease, box-shadow 0.2s ease !important;
                padding: 0 !important;
            }
            #travelsales-bubble:hover {
                transform: scale(1.06) !important;
                box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45) !important;
            }
            #travelsales-bubble.ts-circle {
                width: 62px !important;
                height: 62px !important;
                border-radius: 50% !important;
            }
            #travelsales-bubble.ts-pill {
                height: 52px !important;
                padding: 0 18px 0 10px !important;
                gap: 10px !important;
                border-radius: 30px !important;
            }
            #travelsales-bubble.ts-pos-left {
                right: auto !important;
                left: 24px !important;
            }
            #travelsales-pill-text {
                color: white !important;
                font-size: 0.9rem !important;
                font-weight: 600 !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
                white-space: nowrap !important;
            }
            #travelsales-badge {
                position: absolute !important;
                top: -3px !important;
                right: -3px !important;
                background-color: #ef4444 !important;
                color: white !important;
                font-size: 10px !important;
                font-weight: 700 !important;
                border-radius: 10px !important;
                padding: 2px 6px !important;
                border: 2px solid #ffffff !important;
                animation: ts-pulse 2s infinite !important;
            }
            @keyframes ts-pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.18); }
                100% { transform: scale(1); }
            #travelsales-teaser {
                position: fixed !important;
                bottom: 88px !important;
                right: 24px !important;
                background: #ffffff !important;
                color: #020C21 !important;
                padding: 10px 16px !important;
                border-radius: 14px !important;
                box-shadow: 0 12px 32px rgba(2, 12, 33, 0.18), 0 2px 6px rgba(0,0,0,0.06) !important;
                border: 1px solid rgba(2, 12, 33, 0.08) !important;
                font-size: 0.88rem !important;
                font-weight: 500 !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
                max-width: 280px !important;
                line-height: 1.4 !important;
                z-index: 2147483646 !important;
                cursor: pointer !important;
                display: none;
                align-items: center !important;
                gap: 10px !important;
                animation: ts-teaser-fade 0.35s ease !important;
                transition: transform 0.2s ease !important;
            }
            #travelsales-teaser:hover {
                transform: translateY(-2px) scale(1.02) !important;
            }
            #travelsales-teaser.ts-pos-left {
                right: auto !important;
                left: 24px !important;
            }
            #travelsales-teaser::after {
                content: '' !important;
                position: absolute !important;
                bottom: -7px !important;
                right: 26px !important;
                width: 14px !important;
                height: 14px !important;
                background: #ffffff !important;
                border-right: 1px solid rgba(2, 12, 33, 0.08) !important;
                border-bottom: 1px solid rgba(2, 12, 33, 0.08) !important;
                transform: rotate(45deg) !important;
            }
            #travelsales-teaser.ts-pos-left::after {
                right: auto !important;
                left: 26px !important;
            }
            #travelsales-teaser-close {
                background: none !important;
                border: none !important;
                color: #94a3b8 !important;
                font-size: 16px !important;
                cursor: pointer !important;
                padding: 0 !important;
                line-height: 1 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                width: 18px !important;
                height: 18px !important;
                border-radius: 50% !important;
                flex-shrink: 0 !important;
            }
            #travelsales-teaser-close:hover {
                color: #020C21 !important;
                background: #f1f5f9 !important;
            }
            @keyframes ts-teaser-fade {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }
            #travelsales-window {
                position: fixed !important;
                bottom: 96px !important;
                right: 24px !important;
                width: 380px !important;
                max-width: calc(100vw - 36px) !important;
                height: 540px !important;
                max-height: calc(100vh - 120px) !important;
                border-radius: 16px !important;
                box-shadow: 0 20px 50px rgba(0,0,0,0.4) !important;
                display: none;
                flex-direction: column !important;
                overflow: hidden !important;
                z-index: 2147483647 !important;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
                transition: opacity 0.2s ease, transform 0.2s ease !important;
            }
            #travelsales-window.ts-pos-left {
                right: auto !important;
                left: 24px !important;
            }
            
            /* TEMA OSCURO (Por defecto) */
            .ts-theme-dark {
                background-color: #0f172a !important;
                color: #f8fafc !important;
                border: 1px solid #1e293b !important;
            }
            .ts-theme-dark #travelsales-messages { background-color: #0b1120 !important; }
            .ts-theme-dark .ts-msg-bot { background-color: #1e293b !important; color: #f1f5f9 !important; border: 1px solid #334155 !important; }
            .ts-theme-dark #travelsales-input-bar { background-color: #0f172a !important; border-top: 1px solid #1e293b !important; }
            .ts-theme-dark #travelsales-input { background-color: #1e293b !important; border: 1px solid #334155 !important; color: white !important; }

            /* TEMA CLARO */
            .ts-theme-light {
                background-color: #ffffff !important;
                color: #0f172a !important;
                border: 1px solid #e2e8f0 !important;
            }
            .ts-theme-light #travelsales-messages { background-color: #f8fafc !important; }
            .ts-theme-light .ts-msg-bot { background-color: #ffffff !important; color: #0f172a !important; border: 1px solid #e2e8f0 !important; box-shadow: 0 2px 6px rgba(0,0,0,0.03) !important; }
            .ts-theme-light #travelsales-input-bar { background-color: #ffffff !important; border-top: 1px solid #e2e8f0 !important; }
            .ts-theme-light #travelsales-input { background-color: #f1f5f9 !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; }

            /* TEMA GLASSMORPHISM */
            .ts-theme-glass {
                background: rgba(15, 23, 42, 0.8) !important;
                backdrop-filter: blur(18px) !important;
                -webkit-backdrop-filter: blur(18px) !important;
                color: #f8fafc !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
            }
            .ts-theme-glass #travelsales-messages { background: transparent !important; }
            .ts-theme-glass .ts-msg-bot { background: rgba(30, 41, 59, 0.85) !important; color: #f1f5f9 !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; }
            .ts-theme-glass #travelsales-input-bar { background: rgba(15, 23, 42, 0.9) !important; border-top: 1px solid rgba(255, 255, 255, 0.1) !important; }
            .ts-theme-glass #travelsales-input { background: rgba(30, 41, 59, 0.85) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; color: white !important; }

            #travelsales-header {
                padding: 16px !important;
                display: flex !important;
                align-items: center !important;
                justify-content: space-between !important;
            }
            #travelsales-messages {
                flex: 1 !important;
                padding: 16px !important;
                overflow-y: auto !important;
                display: flex !important;
                flex-direction: column !important;
                gap: 12px !important;
            }
            .ts-msg {
                max-width: 84% !important;
                padding: 10px 14px !important;
                border-radius: 12px !important;
                font-size: 0.9rem !important;
                line-height: 1.52 !important;
                word-wrap: break-word !important;
            }
            .ts-msg strong, .ts-msg b {
                font-weight: 700 !important;
                color: inherit !important;
            }
            .ts-msg em, .ts-msg i {
                font-style: italic !important;
            }
            .ts-msg code {
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
                background: rgba(0, 0, 0, 0.08) !important;
                padding: 2px 5px !important;
                border-radius: 4px !important;
                font-size: 0.88em !important;
            }
            .ts-theme-dark .ts-msg code {
                background: rgba(255, 255, 255, 0.15) !important;
            }
            .ts-msg a {
                color: inherit !important;
                text-decoration: underline !important;
                font-weight: 600 !important;
            }
            .ts-msg-bot {
                align-self: flex-start !important;
                border-bottom-left-radius: 2px !important;
            }
            .ts-msg-user {
                background-color: var(--ts-brand-color, #2563eb) !important;
                color: #ffffff !important;
                align-self: flex-end !important;
                border-bottom-right-radius: 2px !important;
            }
            .ts-checkout-btn {
                display: inline-block !important;
                margin-top: 10px !important;
                padding: 10px 16px !important;
                background-color: #635bff !important;
                color: white !important;
                text-decoration: none !important;
                border-radius: 8px !important;
                font-weight: bold !important;
                font-size: 0.85rem !important;
                box-shadow: 0 4px 12px rgba(99, 91, 255, 0.3) !important;
            }
            #travelsales-input-bar {
                display: flex !important;
                padding: 12px !important;
                gap: 8px !important;
            }
            #travelsales-input {
                flex: 1 !important;
                padding: 10px 16px !important;
                border-radius: 22px !important;
                font-size: 0.9rem !important;
                outline: none !important;
            }
            #travelsales-send {
                background-color: #2563eb !important;
                color: white !important;
                border: none !important;
                border-radius: 50% !important;
                width: 40px !important;
                height: 40px !important;
                cursor: pointer !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                flex-shrink: 0 !important;
            }

            /* Carrusel Interactivo de Tarjetas en Widget */
            .chat-carousel-wrapper {
                margin: 4px 0 6px 0 !important;
                width: 100% !important;
                max-width: 100% !important;
                overflow: hidden !important;
            }
            .chat-carousel-header {
                display: flex !important;
                justify-content: space-between !important;
                align-items: center !important;
                padding: 0 4px 6px 4px !important;
            }
            .chat-carousel-count {
                font-size: 11px !important;
                font-weight: 700 !important;
                color: #94A3B8 !important;
                letter-spacing: 0.6px !important;
                text-transform: uppercase !important;
            }
            .chat-carousel-hint {
                font-size: 11px !important;
                font-weight: 600 !important;
                color: #94A3B8 !important;
            }
            .chat-carousel-track {
                display: flex !important;
                gap: 12px !important;
                overflow-x: auto !important;
                scroll-snap-type: x mandatory !important;
                padding: 4px 4px 10px 4px !important;
                -webkit-overflow-scrolling: touch !important;
                scrollbar-width: thin !important;
            }
            .chat-carousel-track::-webkit-scrollbar {
                height: 5px !important;
            }
            .chat-carousel-track::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.05) !important;
                border-radius: 4px !important;
            }
            .chat-carousel-track::-webkit-scrollbar-thumb {
                background: #CBD5E1 !important;
                border-radius: 4px !important;
            }
            .chat-card-item {
                flex: 0 0 220px !important;
                width: 220px !important;
                min-width: 220px !important;
                scroll-snap-align: start !important;
                background: #FFFFFF !important;
                border: 1px solid #E2E8F0 !important;
                border-radius: 18px !important;
                overflow: hidden !important;
                box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08) !important;
                display: flex !important;
                flex-direction: column !important;
                transition: transform 0.16s ease, box-shadow 0.16s ease !important;
            }
            .ts-theme-dark .chat-card-item {
                background: #1E293B !important;
                border-color: #334155 !important;
            }
            .chat-card-item:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 20px rgba(15, 23, 42, 0.14) !important;
            }
            .chat-card-img-wrap {
                height: 130px !important;
                width: 100% !important;
                background-size: cover !important;
                background-position: center !important;
                position: relative !important;
                background-color: #0F172A !important;
            }
            .chat-card-gradient {
                position: absolute !important;
                inset: 0 !important;
                background: linear-gradient(180deg, rgba(0,0,0,0.08) 0%, rgba(0,0,0,0.18) 45%, rgba(0,0,0,0.85) 100%) !important;
            }
            .chat-card-badge {
                position: absolute !important;
                top: 9px !important;
                right: 9px !important;
                background: rgba(15, 23, 42, 0.65) !important;
                backdrop-filter: blur(6px) !important;
                -webkit-backdrop-filter: blur(6px) !important;
                color: #FFFFFF !important;
                font-size: 11px !important;
                font-weight: 600 !important;
                padding: 3px 9px !important;
                border-radius: 20px !important;
                z-index: 2 !important;
                border: 1px solid rgba(255, 255, 255, 0.25) !important;
            }
            .chat-card-img-title {
                position: absolute !important;
                bottom: 9px !important;
                left: 12px !important;
                right: 12px !important;
                color: #FFFFFF !important;
                font-weight: 700 !important;
                font-size: 14.5px !important;
                text-shadow: 0 1px 3px rgba(0,0,0,0.7) !important;
                z-index: 2 !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            .chat-card-no-img {
                padding: 16px 12px 12px 12px !important;
                background: linear-gradient(135deg, #0F1B31 0%, #1E293B 100%) !important;
                position: relative !important;
            }
            .chat-card-no-img-title {
                color: #FFFFFF !important;
                font-weight: 700 !important;
                font-size: 14.5px !important;
            }
            .chat-card-body {
                padding: 12px !important;
                display: flex !important;
                flex-direction: column !important;
                gap: 8px !important;
                flex: 1 !important;
                background: #FFFFFF !important;
            }
            .ts-theme-dark .chat-card-body {
                background: #1E293B !important;
            }
            .chat-card-specs-row {
                display: grid !important;
                grid-template-columns: repeat(3, 1fr) !important;
                gap: 6px !important;
                padding-bottom: 2px !important;
            }
            .chat-card-spec-col {
                display: flex !important;
                flex-direction: column !important;
                gap: 1px !important;
            }
            .chat-card-spec-lbl {
                font-size: 9px !important;
                font-weight: 700 !important;
                color: #94A3B8 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.4px !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            .chat-card-spec-val {
                font-size: 12.5px !important;
                font-weight: 700 !important;
                color: #0F172A !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
            .ts-theme-dark .chat-card-spec-val {
                color: #F8FAFC !important;
            }
            .chat-card-tags-row {
                display: flex !important;
                flex-wrap: wrap !important;
                gap: 4px !important;
            }
            .chat-card-tag {
                background: #F1F5F9 !important;
                color: #334155 !important;
                font-size: 10.5px !important;
                font-weight: 500 !important;
                padding: 3px 8px !important;
                border-radius: 12px !important;
                white-space: nowrap !important;
            }
            .ts-theme-dark .chat-card-tag {
                background: #334155 !important;
                color: #E2E8F0 !important;
            }
            .chat-card-tag.more {
                background: #E2E8F0 !important;
                color: #475569 !important;
                font-weight: 600 !important;
            }
            .chat-card-action-btn {
                background: none !important;
                border: none !important;
                padding: 6px 0 0 0 !important;
                color: #2563EB !important;
                font-weight: 700 !important;
                font-size: 13px !important;
                cursor: pointer !important;
                text-align: left !important;
                display: inline-flex !important;
                align-items: center !important;
                gap: 4px !important;
                transition: color 0.15s ease !important;
                margin-top: auto !important;
            }
            .chat-card-action-btn:hover {
                color: #1D4ED8 !important;
                text-decoration: underline !important;
            }

            /* Formulario de Captura de Leads Directo en Chat */
            .chat-lead-card {
                background: #FFFFFF !important;
                border: 1.5px solid #E2E8F0 !important;
                border-radius: 14px !important;
                padding: 14px 16px !important;
                margin: 10px 0 !important;
                max-width: 90% !important;
                box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08) !important;
                font-family: inherit !important;
            }
            .ts-theme-dark .chat-lead-card {
                background: #1E293B !important;
                border-color: #334155 !important;
            }
            .chat-lead-badge {
                display: inline-flex !important;
                align-items: center !important;
                gap: 5px !important;
                font-size: 11px !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
                color: #2563EB !important;
                margin-bottom: 4px !important;
            }
            .chat-lead-subtitle {
                font-size: 12px !important;
                color: #64748B !important;
                margin: 0 0 10px 0 !important;
                line-height: 1.35 !important;
            }
            .ts-theme-dark .chat-lead-subtitle {
                color: #94A3B8 !important;
            }
            .chat-lead-body {
                display: flex !important;
                flex-direction: column !important;
                gap: 8px !important;
            }
            .chat-lead-input {
                width: 100% !important;
                padding: 8px 12px !important;
                border-radius: 8px !important;
                border: 1px solid #CBD5E1 !important;
                font-size: 13px !important;
                box-sizing: border-box !important;
                background: #F8FAFC !important;
                color: #0F172A !important;
                font-family: inherit !important;
                outline: none !important;
            }
            .ts-theme-dark .chat-lead-input {
                background: #0F172A !important;
                border-color: #334155 !important;
                color: #F8FAFC !important;
            }
            .chat-lead-input:focus {
                border-color: #2563EB !important;
                background: #FFFFFF !important;
            }
            .chat-lead-submit {
                background: #2563EB !important;
                color: #FFFFFF !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 9px 14px !important;
                font-weight: 600 !important;
                font-size: 13px !important;
                cursor: pointer !important;
                transition: opacity 0.2s ease !important;
                margin-top: 2px !important;
                text-align: center !important;
            }
            .chat-lead-submit:hover {
                opacity: 0.9 !important;
            }
            .chat-lead-success {
                background: rgba(16, 185, 129, 0.12) !important;
                border: 1px solid rgba(16, 185, 129, 0.3) !important;
                color: #047857 !important;
                border-radius: 8px !important;
                padding: 10px !important;
                font-size: 12px !important;
                text-align: center !important;
            }
            .ts-theme-dark .chat-lead-success {
                color: #34D399 !important;
            }
        `;
        document.head.appendChild(style);

        // Crear elementos DOM
        const isKlyven = tenantId.toUpperCase().includes('KLYVEN');
        const defaultTitle = isKlyven ? 'Klyven Assistant' : 'Asistente Oficial';
        const defaultWelcome = isKlyven 
            ? '¡Hola! Bienvenido a Klyven Studio. ¿Qué tipo de sitio web o proyecto te gustaría cotizar hoy?' 
            : '¡Hola! ¿En qué te podemos asesorar o ayudar hoy?';

        const bubble = document.createElement('div');
        bubble.id = 'travelsales-bubble';
        bubble.className = 'ts-circle';
        bubble.innerHTML = `
            <div id="travelsales-bubble-avatar" style="width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center; overflow:hidden; font-size:1.3rem;">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
            </div>
            <span id="travelsales-pill-text" style="display:none;">Hablemos de tu web</span>
            <div id="travelsales-badge">1</div>
        `;

        const windowDiv = document.createElement('div');
        windowDiv.id = 'travelsales-window';
        windowDiv.className = 'ts-theme-dark';
        windowDiv.innerHTML = `
            <div id="travelsales-header" style="background: #2563eb;">
                <div style="display:flex; align-items:center; gap:10px;">
                    <div id="travelsales-avatar-icon" style="width:36px; height:36px; border-radius:50%; background:white; color:#0F1B31; font-weight:800; display:flex; align-items:center; justify-content:center; font-size:1rem; overflow:hidden; flex-shrink:0;">K</div>
                    <div>
                        <div class="ts-header-title" style="font-weight:bold; font-size:0.95rem; color:white;">${defaultTitle}</div>
                        <div style="font-size:0.75rem; color:#e0f2fe; display:flex; align-items:center; gap:5px;"><span style="width:6px; height:6px; border-radius:50%; background:#10B981; display:inline-block;"></span> En línea</div>
                    </div>
                </div>
                <div id="travelsales-close" style="cursor:pointer; display:flex; align-items:center; justify-content:center; color:#cbd5e1;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></div>
            </div>
            <div id="travelsales-messages">
                <div class="ts-msg ts-msg-bot ts-first-msg">${defaultWelcome}</div>
            </div>
            <div id="travelsales-input-bar">
                <input id="travelsales-input" type="text" placeholder="Escribe tu consulta..." />
                <button id="travelsales-send"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
            </div>
        `;

        const teaser = document.createElement('div');
        teaser.id = 'travelsales-teaser';
        teaser.innerHTML = `
            <span id="travelsales-teaser-text">👋 ¿Tienes dudas sobre tu web? Pregúntame aquí</span>
            <button id="travelsales-teaser-close" title="Cerrar">×</button>
        `;

        document.body.appendChild(teaser);
        document.body.appendChild(bubble);
        document.body.appendChild(windowDiv);

        // Lógica de apertura
        function toggleChat() {
            const isHidden = windowDiv.style.display === 'none' || !windowDiv.style.display;
            windowDiv.style.display = isHidden ? 'flex' : 'none';
            if (isHidden) {
                if (teaser) teaser.style.display = 'none';
                const badge = document.getElementById('travelsales-badge');
                if (badge) badge.style.display = 'none';
                setTimeout(() => {
                    const inputEl = document.getElementById('travelsales-input');
                    if (inputEl) inputEl.focus();
                }, 100);
            }
        }

        bubble.onclick = toggleChat;
        teaser.onclick = (e) => {
            if (e.target.id === 'travelsales-teaser-close') {
                e.stopPropagation();
                teaser.style.display = 'none';
                return;
            }
            toggleChat();
        };
        const teaserCloseBtn = document.getElementById('travelsales-teaser-close');
        if (teaserCloseBtn) {
            teaserCloseBtn.onclick = (e) => {
                e.stopPropagation();
                teaser.style.display = 'none';
            };
        }
        document.getElementById('travelsales-close').onclick = () => {
            windowDiv.style.display = 'none';
        };

        window.openKlyvenChat = toggleChat;
        window.openTravelSalesChat = toggleChat;

        let activeBrandColor = '#2563eb';

        // Cargar Configuración Dinámica y Personalización Libre
        fetch(`${apiBase}/api/tenant-config?tenant_id=${encodeURIComponent(tenantId)}`)
            .then(res => res.json())
            .then(cfg => {
                if (!cfg) return;

                // 1. Colores (Manual o Auto-Adaptado)
                let brandColor = cfg.brand_color || '#2563eb';
                if (cfg.auto_adapt || forceAutoTheme) {
                    const detected = detectHostPageColor();
                    if (detected) brandColor = detected;
                }
                activeBrandColor = brandColor;

                // 2. Aplicar Color de Marca
                document.documentElement.style.setProperty('--ts-brand-color', brandColor);
                if (windowDiv) windowDiv.style.setProperty('--ts-brand-color', brandColor);
                const headerEl = document.getElementById('travelsales-header');
                const sendBtn = document.getElementById('travelsales-send');
                if (headerEl) headerEl.style.backgroundColor = brandColor;
                if (bubble) bubble.style.background = brandColor;
                if (sendBtn) sendBtn.style.backgroundColor = brandColor;
                document.querySelectorAll('.ts-msg-user').forEach(el => {
                    el.style.backgroundColor = brandColor;
                });

                // 3. Tema (Dark, Light, Glass)
                const themeMode = cfg.theme_mode || 'dark';
                windowDiv.className = `ts-theme-${themeMode}`;
                if (cfg.border_radius) {
                    windowDiv.style.borderRadius = `${cfg.border_radius}px`;
                }

                // 4. Posición (Left / Right)
                if (cfg.position === 'bottom-left') {
                    bubble.classList.add('ts-pos-left');
                    windowDiv.classList.add('ts-pos-left');
                }

                // 5. Estilo de Burbuja (Circle / Pill)
                if (cfg.bubble_style === 'pill') {
                    bubble.className = 'ts-pill' + (cfg.position === 'bottom-left' ? ' ts-pos-left' : '');
                    const pillTextEl = document.getElementById('travelsales-pill-text');
                    if (pillTextEl) {
                        pillTextEl.innerText = cfg.bubble_text || 'Hablemos de tu web';
                        pillTextEl.style.display = 'inline-block';
                    }
                }

                // 6. Avatar / Foto
                const avatarIconEl = document.getElementById('travelsales-avatar-icon');
                const bubbleAvEl = document.getElementById('travelsales-bubble-avatar');
                if (cfg.bot_avatar) {
                    const isImg = cfg.bot_avatar.startsWith('http') || cfg.bot_avatar.startsWith('/') || cfg.bot_avatar.startsWith('./') || cfg.bot_avatar.startsWith('data:');
                    const imgHtml = `<img src="${cfg.bot_avatar}" alt="Avatar" style="width:100%;height:100%;object-fit:cover;border-radius:50%;display:block;" />`;
                    if (isImg) {
                        if (avatarIconEl) avatarIconEl.innerHTML = imgHtml;
                        if (bubbleAvEl) bubbleAvEl.innerHTML = imgHtml;
                    } else {
                        if (avatarIconEl) avatarIconEl.innerText = cfg.bot_avatar;
                        if (bubbleAvEl) bubbleAvEl.innerText = cfg.bot_avatar;
                    }
                }

                // 7. Textos
                const headerTitleEl = document.querySelector('#travelsales-header .ts-header-title');
                if (headerTitleEl && cfg.bot_name) {
                    headerTitleEl.innerText = `${cfg.bot_name} • ${cfg.business_name || ''}`;
                }
                const firstMsg = document.querySelector('#travelsales-messages .ts-first-msg');
                if (firstMsg && cfg.welcome_message) {
                    firstMsg.innerHTML = formatRichText(cfg.welcome_message);
                }
                const inputEl = document.getElementById('travelsales-input');
                if (inputEl && cfg.input_placeholder) {
                    inputEl.setAttribute('placeholder', cfg.input_placeholder);
                }

                // 8. Geometría de Bordes
                if (cfg.border_radius) {
                    const r = parseInt(cfg.border_radius) || 16;
                    windowDiv.style.borderRadius = `${r}px`;
                    const bRadius = (r <= 8 ? 6 : (r >= 24 ? 22 : 14));
                    const iRadius = (r <= 8 ? 6 : (r >= 24 ? 22 : 18));
                    const btnR = (r <= 8 ? '6px' : '50%');
                    document.querySelectorAll('.ts-msg').forEach(el => {
                        el.style.borderRadius = `${bRadius}px`;
                    });
                    if (inputEl) inputEl.style.borderRadius = `${iRadius}px`;
                    const sendBtnEl = document.getElementById('travelsales-send');
                    if (sendBtnEl) sendBtnEl.style.borderRadius = btnR;
                    if (bubble && cfg.bubble_style === 'pill' && r <= 8) {
                        bubble.style.borderRadius = '10px';
                    }
                }

                // 9. Globo de Saludo Proactivo (Teaser Pop)
                if (cfg.teaser_enabled) {
                    const teaserText = document.getElementById('travelsales-teaser-text');
                    if (teaserText && cfg.teaser_text) {
                        teaserText.innerText = cfg.teaser_text;
                    }
                    if (cfg.position === 'bottom-left' && teaser) {
                        teaser.classList.add('ts-pos-left');
                    }
                    const delaySec = parseInt(cfg.teaser_delay) || 4;
                    setTimeout(() => {
                        const isChatOpen = windowDiv && (windowDiv.style.display === 'flex');
                        if (!isChatOpen && teaser) {
                            teaser.style.display = 'flex';
                        }
                    }, delaySec * 1000);
                }
            })
            .catch(() => {});

        function escapeHtml(text) {
            if (!text) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function renderCarouselHtml(jsonStr) {
            try {
                const items = typeof jsonStr === 'string' ? JSON.parse(jsonStr.trim()) : jsonStr;
                if (!Array.isArray(items) || items.length === 0) return '';

                const countText = `${items.length} ${items.length === 1 ? 'OPCIÓN' : 'UNIDADES / OPCIONES'}`;

                let cardsHtml = items.map(item => {
                    const title = escapeHtml(item.title || item.name || 'Servicio');
                    const imgUrl = item.image || item.image_url || '';
                    const badge = item.badge || (imgUrl ? 'Foto' : '');
                    const price = item.price ? (typeof item.price === 'number' ? `$${item.price}` : item.price) : '';
                    const actionLabel = escapeHtml(item.action_label || 'Ver más');
                    const actionQuery = (item.action_query || `Me interesa ${title}`).replace(/"/g, '&quot;');

                    // Fila de especificaciones (3 columnas)
                    let specsHtml = '';
                    if (Array.isArray(item.specs) && item.specs.length > 0) {
                        const cols = item.specs.slice(0, 3).map(sp => `
                            <div class="chat-card-spec-col">
                                <span class="chat-card-spec-lbl">${escapeHtml(sp.label || '')}</span>
                                <span class="chat-card-spec-val">${escapeHtml(sp.val || sp.value || '')}</span>
                            </div>
                        `).join('');
                        specsHtml = `<div class="chat-card-specs-row">${cols}</div>`;
                    } else if (price) {
                        specsHtml = `
                            <div class="chat-card-specs-row">
                                <div class="chat-card-spec-col">
                                    <span class="chat-card-spec-lbl">PRECIO</span>
                                    <span class="chat-card-spec-val">${escapeHtml(price)}</span>
                                </div>
                                <div class="chat-card-spec-col">
                                    <span class="chat-card-spec-lbl">ESTADO</span>
                                    <span class="chat-card-spec-val">Disponible</span>
                                </div>
                            </div>
                        `;
                    }

                    // Tags / Chips de amenidades
                    let tagsList = [];
                    if (Array.isArray(item.tags)) {
                        tagsList = item.tags;
                    } else if (typeof item.description === 'string' && item.description.includes('|')) {
                        const parts = item.description.split('|');
                        tagsList = parts[parts.length - 1].split(',').map(t => t.trim());
                    } else if (typeof item.description === 'string') {
                        tagsList = item.description.split(',').map(t => t.trim()).filter(Boolean);
                    }

                    let tagsHtml = '';
                    if (tagsList.length > 0) {
                        const visible = tagsList.slice(0, 3);
                        const remaining = tagsList.length - 3;
                        const chips = visible.map(t => `<span class="chat-card-tag">${escapeHtml(t)}</span>`).join('');
                        const moreBadge = remaining > 0 ? `<span class="chat-card-tag more">+${remaining}</span>` : '';
                        tagsHtml = `<div class="chat-card-tags-row">${chips}${moreBadge}</div>`;
                    }

                    // Cabecera visual (con foto o degradado)
                    const imgHeader = imgUrl ? `
                        <div class="chat-card-img-wrap" style="background-image: url('${encodeURI(imgUrl)}');">
                            <div class="chat-card-gradient"></div>
                            ${badge ? `<div class="chat-card-badge">${escapeHtml(badge)}</div>` : ''}
                            <div class="chat-card-img-title">${title}</div>
                        </div>
                    ` : `
                        <div class="chat-card-no-img">
                            ${badge ? `<div class="chat-card-badge">${escapeHtml(badge)}</div>` : ''}
                            <div class="chat-card-no-img-title">${title}</div>
                        </div>
                    `;

                    return `
                        <div class="chat-card-item">
                            ${imgHeader}
                            <div class="chat-card-body">
                                ${specsHtml}
                                ${tagsHtml}
                                <button class="chat-card-action-btn" type="button" onclick="window.__tsQuickAsk ? window.__tsQuickAsk('${actionQuery.replace(/'/g, "\\'")}') : null">
                                    ${actionLabel} →
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');

                return `
                    <div class="chat-carousel-wrapper">
                        <div class="chat-carousel-header">
                            <span class="chat-carousel-count">${countText}</span>
                            <span class="chat-carousel-hint">Desliza →</span>
                        </div>
                        <div class="chat-carousel-track">
                            ${cardsHtml}
                        </div>
                    </div>
                `;
            } catch(e) {
                console.error('Error procesando carrusel JSON en widget:', e);
                return '';
            }
        }

        function renderLeadFormWidgetHtml(jsonStr) {
            try {
                const data = JSON.parse(jsonStr.trim());
                const title = data.title || 'Cotización Inmediata';
                const subtitle = data.subtitle || 'Déjanos tus datos y un especialista te contactará a la brevedad.';
                const service = data.service_interest || '';
                const formId = 'ts_lead_' + Math.random().toString(36).substring(2, 9);

                return `
                    <div class="chat-lead-card" id="${formId}">
                        <div class="chat-lead-badge">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            ${title}
                        </div>
                        <p class="chat-lead-subtitle">${subtitle}</p>
                        ${service ? `<div style="font-size:11px;font-weight:700;color:${activeBrandColor || '#2563EB'};margin-bottom:8px;background:rgba(37,99,235,0.08);padding:3px 8px;border-radius:6px;">Interés: ${service}</div>` : ''}
                        
                        <div class="chat-lead-body" id="${formId}_fields">
                            <input type="text" class="chat-lead-input" id="${formId}_name" placeholder="Tu Nombre o Empresa *" required />
                            <input type="tel" class="chat-lead-input" id="${formId}_phone" placeholder="WhatsApp o Teléfono (10 dígitos) *" required />
                            <input type="text" class="chat-lead-input" id="${formId}_notes" placeholder="Detalles o requerimientos (opcional)" />
                            <button type="button" class="chat-lead-submit" style="background:${activeBrandColor || '#2563EB'} !important;" onclick="window.__tsSubmitLead ? window.__tsSubmitLead('${formId}', '${service.replace(/'/g, "\\'")}') : null">
                                Enviar Solicitud de Cotización
                            </button>
                        </div>
                        <div class="chat-lead-success" id="${formId}_success" style="display:none;"></div>
                    </div>
                `;
            } catch (e) {
                console.error('Error parseando lead_form JSON en widget:', e);
                return '';
            }
        }

        function formatRichText(raw) {
            if (!raw) return '';
            let str = String(raw);

            // Reemplazo limpio si existiera carrusel
            str = str.replace(/:::carousel\s*([\s\S]*?)\s*:::/g, (match, jsonStr) => {
                return renderCarouselHtml(jsonStr);
            });
            str = str.replace(/:::lead_form\s*([\s\S]*?)\s*:::/g, (match, jsonStr) => {
                return renderLeadFormWidgetHtml(jsonStr);
            });

            str = str.replace(/([^\n])\s+(\d+\.\s+\*\*)/g, (m, p1, p2) => p1 + '\n\n' + p2);
            str = str.replace(/([^\n])\s+([\-\*]\s+\*\*)/g, (m, p1, p2) => p1 + '\n\n' + p2);
            str = str.replace(/^###\s+(.*?)$/gm, '<div style="font-weight:700;font-size:1.02em;margin:6px 0 2px 0;">$1</div>');
            str = str.replace(/^##\s+(.*?)$/gm, '<div style="font-weight:700;font-size:1.06em;margin:6px 0 2px 0;">$1</div>');
            str = str.replace(/^#\s+(.*?)$/gm, '<div style="font-weight:800;font-size:1.1em;margin:8px 0 3px 0;">$1</div>');
            str = str.replace(/\*\*\*(.*?)\*\*\*/g, (m, p) => '<strong><em>' + p + '</em></strong>');
            str = str.replace(/\*\*(.*?)\*\*/g, (m, p) => '<strong>' + p + '</strong>');
            str = str.replace(/__(.*?)__/g, (m, p) => '<strong>' + p + '</strong>');
            str = str.replace(/(^|[^\*])\*(?!\*)([^\*]+)\*(?!\*)/g, (m, p1, p2) => p1 + '<em>' + p2 + '</em>');
            str = str.replace(/(^|[^_])_(?!_)([^_]+)_(?!_)/g, (m, p1, p2) => p1 + '<em>' + p2 + '</em>');
            str = str.replace(/~~(.*?)~~/g, (m, p) => '<del>' + p + '</del>');
            str = str.replace(/\`([^\`]+)\`/g, (m, p) => '<code>' + p + '</code>');
            str = str.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, (m, p1, p2) => {
                if (p2.includes('wa.me')) {
                    return '<a href="' + p2 + '" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:6px;background:#25D366;color:#ffffff !important;font-weight:600;padding:8px 14px;border-radius:12px;text-decoration:none;margin-top:6px;box-shadow:0 2px 6px rgba(37,211,102,0.3);">' + p1 + '</a>';
                }
                if (p1.includes('Agendar') || p2.includes('calendly.com') || p2.includes('cal.com')) {
                    return '<a href="' + p2 + '" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:6px;background:#4F46E5;color:#ffffff !important;font-weight:600;padding:8px 14px;border-radius:12px;text-decoration:none;margin-top:6px;box-shadow:0 2px 8px rgba(79,70,229,0.35);">' + p1 + '</a>';
                }
                return '<a href="' + p2 + '" target="_blank" rel="noopener noreferrer">' + p1 + '</a>';
            });
            str = str.replace(/\n\n+/g, '<div style="height:8px;"></div>');
            str = str.replace(/\n/g, '<br>');
            return str;
        }

        // Lógica de Envío de Mensajes
        const input = document.getElementById('travelsales-input');
        const sendBtn = document.getElementById('travelsales-send');
        const msgBox = document.getElementById('travelsales-messages');

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            const userEl = document.createElement('div');
            userEl.className = 'ts-msg ts-msg-user';
            userEl.style.backgroundColor = activeBrandColor;
            userEl.innerHTML = formatRichText(text);
            msgBox.appendChild(userEl);
            input.value = '';
            msgBox.scrollTop = msgBox.scrollHeight;

            conversationHistory.push({ role: 'user', content: text });

            const typingEl = document.createElement('div');
            typingEl.className = 'ts-msg ts-msg-bot';
            typingEl.innerText = 'Consultando...';
            msgBox.appendChild(typingEl);
            msgBox.scrollTop = msgBox.scrollHeight;

            try {
                let sessionId = localStorage.getItem('ts_session_' + tenantId);
                if (!sessionId) {
                    sessionId = 'sess_' + Math.random().toString(36).substring(2, 12);
                    localStorage.setItem('ts_session_' + tenantId, sessionId);
                }

                const resp = await fetch(`${apiBase}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tenant_id: tenantId,
                        message: text,
                        session_id: sessionId,
                        history: conversationHistory
                    })
                });
                const data = await resp.json();
                msgBox.removeChild(typingEl);

                let replyStr = String(data.reply || '');
                let leadFormHtml = '';
                let carouselHtml = '';

                const lMatch = replyStr.match(/:::lead_form\s*([\s\S]*?)\s*:::/);
                if (lMatch) {
                    leadFormHtml = renderLeadFormWidgetHtml(lMatch[1]);
                    replyStr = replyStr.replace(/:::lead_form\s*([\s\S]*?)\s*:::/g, '').trim();
                }

                const cMatch = replyStr.match(/:::carousel\s*([\s\S]*?)\s*:::/);
                if (cMatch) {
                    carouselHtml = renderCarouselHtml(cMatch[1]);
                    replyStr = replyStr.replace(/:::carousel\s*([\s\S]*?)\s*:::/g, '').trim();
                }

                if (replyStr) {
                    const botEl = document.createElement('div');
                    botEl.className = 'ts-msg ts-msg-bot';
                    botEl.innerHTML = formatRichText(replyStr);
                    msgBox.appendChild(botEl);
                }

                if (carouselHtml) {
                    const cDiv = document.createElement('div');
                    cDiv.className = 'chat-carousel-wrapper';
                    cDiv.innerHTML = carouselHtml;
                    msgBox.appendChild(cDiv);
                }

                if (leadFormHtml) {
                    const lDiv = document.createElement('div');
                    lDiv.innerHTML = leadFormHtml;
                    const cardEl = lDiv.firstElementChild || lDiv;
                    msgBox.appendChild(cardEl);
                }

                if (data.checkout_url) {
                    const btn = document.createElement('a');
                    btn.className = 'ts-checkout-btn';
                    btn.href = data.checkout_url;
                    btn.target = '_blank';
                    btn.innerText = `Pagar y Confirmar ($${data.price} ${data.currency})`;
                    msgBox.appendChild(btn);
                }

                conversationHistory.push({ role: 'assistant', content: data.reply });
                msgBox.scrollTop = msgBox.scrollHeight;
            } catch (err) {
                if (msgBox.contains(typingEl)) msgBox.removeChild(typingEl);
                const errEl = document.createElement('div');
                errEl.className = 'ts-msg ts-msg-bot';
                errEl.innerText = 'Lo sentimos, hubo un inconveniente al conectar con el servidor.';
                msgBox.appendChild(errEl);
            }
        }

        window.__tsSubmitLead = async function(formId, serviceInterest) {
            const nameEl = document.getElementById(formId + '_name');
            const phoneEl = document.getElementById(formId + '_phone');
            const notesEl = document.getElementById(formId + '_notes');
            const fieldsEl = document.getElementById(formId + '_fields');
            const successEl = document.getElementById(formId + '_success');

            const name = nameEl?.value?.trim();
            const phone = phoneEl?.value?.trim();
            const notes = notesEl?.value?.trim() || '';

            if (!name) {
                alert('Por favor ingresa tu nombre.');
                nameEl?.focus();
                return;
            }
            if (!phone || phone.length < 7) {
                alert('Por favor ingresa un número de teléfono o WhatsApp válido.');
                phoneEl?.focus();
                return;
            }

            const btn = fieldsEl ? fieldsEl.querySelector('button') : null;
            if (btn) {
                btn.disabled = true;
                btn.innerText = 'Enviando...';
            }

            try {
                let sessionId = localStorage.getItem('ts_session_' + tenantId) || 'widget-lead';
                const res = await fetch(`${apiBase}/api/leads/submit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tenant_id: tenantId,
                        name: name,
                        phone: phone,
                        notes: (serviceInterest ? `[Interés: ${serviceInterest}] ` : '') + notes,
                        session_id: sessionId
                    })
                });

                const data = await res.json();
                if (data.status === 'ok') {
                    if (fieldsEl) fieldsEl.style.display = 'none';
                    if (successEl) {
                        successEl.style.display = 'block';
                        successEl.innerHTML = `
                            <div style="font-weight:700;font-size:12px;margin-bottom:2px;">¡Solicitud enviada con éxito!</div>
                            <div style="font-size:11px;opacity:0.9;">${data.message || 'Nos pondremos en contacto contigo a la brevedad.'}</div>
                        `;
                    }
                } else {
                    alert('Error al enviar: ' + (data.detail || 'Ocurrió un error.'));
                    if (btn) {
                        btn.disabled = false;
                        btn.innerText = 'Enviar Solicitud de Cotización';
                    }
                }
            } catch (err) {
                alert('Error al enviar solicitud: ' + err.message);
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = 'Enviar Solicitud de Cotización';
                }
            }
        };

        window.__tsQuickAsk = function(query) {
            if (input && query) {
                input.value = query;
                sendMessage();
            }
        };

        sendBtn.onclick = sendMessage;
        input.onkeypress = (e) => {
            if (e.key === 'Enter') sendMessage();
        };
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }
})();
