class MenuInterface {
    constructor() {
        this.primaryMenu = document.getElementById('menu-primary');
        this.secondaryMenu = document.getElementById('menu-secondary');
        this.primaryIcon = document.getElementById('primary-icon');
        
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        this.transitionDelay = 300; // 300ms conforme especificado
        
        this.init();
    }
    
    init() {
        this.setupPrimaryMenu();
        this.setupSecondaryMenu();
        this.setupEventListeners();
        
        // Inicia com o menu primário visível
        this.showPrimaryMenu();
    }
    
    setupPrimaryMenu() {
        // Configura o arrasto do menu primário
        this.primaryIcon.addEventListener('mousedown', (e) => {
            // Clique esquerdo não faz nada (conforme especificação)
            if (e.button === 0) {
                this.startDrag(e);
            }
        });
        
        // Clique direito abre menu secundário
        this.primaryIcon.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.switchToSecondary();
        });
    }
    
    setupSecondaryMenu() {
        const buttons = this.secondaryMenu.querySelectorAll('.secondary-btn');
        
        buttons.forEach(button => {
            button.addEventListener('click', (e) => {
                const action = e.currentTarget.getAttribute('data-action');
                this.handleSecondaryAction(action);
            });
        });
    }
    
    setupEventListeners() {
        // Eventos globais para arrasto
        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.drag(e);
            }
        });
        
        document.addEventListener('mouseup', () => {
            if (this.isDragging) {
                this.stopDrag();
            }
        });
        
        // Prevenir seleção de texto durante arrasto
        document.addEventListener('selectstart', (e) => {
            if (this.isDragging) {
                e.preventDefault();
            }
        });
    }
    
    startDrag(e) {
        this.isDragging = true;
        this.primaryMenu.classList.add('dragging', 'no-select');
        
        const rect = this.primaryMenu.getBoundingClientRect();
        this.dragOffset.x = e.clientX - rect.left;
        this.dragOffset.y = e.clientY - rect.top;
        
        document.body.style.cursor = 'move';
    }
    
    drag(e) {
        if (!this.isDragging) return;
        
        const newX = e.clientX - this.dragOffset.x;
        const newY = e.clientY - this.dragOffset.y;
        
        // Limites da tela
        const maxX = window.innerWidth - this.primaryMenu.offsetWidth;
        const maxY = window.innerHeight - this.primaryMenu.offsetHeight;
        
        const constrainedX = Math.max(0, Math.min(maxX, newX));
        const constrainedY = Math.max(0, Math.min(maxY, newY));
        
        this.primaryMenu.style.left = constrainedX + 'px';
        this.primaryMenu.style.top = constrainedY + 'px';
        this.primaryMenu.style.transform = 'none';
    }
    
    stopDrag() {
        this.isDragging = false;
        this.primaryMenu.classList.remove('dragging', 'no-select');
        document.body.style.cursor = '';
    }
    
    switchToSecondary() {
        // Fecha menu primário
        this.primaryMenu.classList.add('fade-out');
        
        // Após delay, mostra menu secundário
        setTimeout(() => {
            this.primaryMenu.classList.add('hidden');
            this.primaryMenu.classList.remove('fade-out');
            
            this.secondaryMenu.classList.remove('hidden');
            this.secondaryMenu.classList.add('fade-in');
        }, this.transitionDelay);
    }
    
    switchToPrimary() {
        // Fecha menu secundário
        this.secondaryMenu.classList.add('fade-out');
        
        // Após delay, mostra menu primário
        setTimeout(() => {
            this.secondaryMenu.classList.add('hidden');
            this.secondaryMenu.classList.remove('fade-out');
            
            this.primaryMenu.classList.remove('hidden');
            this.primaryMenu.classList.add('fade-in');
            
            // Remove fade-in após transição
            setTimeout(() => {
                this.primaryMenu.classList.remove('fade-in');
            }, 300);
        }, this.transitionDelay);
    }
    
    showPrimaryMenu() {
        this.primaryMenu.classList.remove('hidden');
        this.secondaryMenu.classList.add('hidden');
    }
    
    handleSecondaryAction(action) {
        switch (action) {
            case 'back':
                this.switchToPrimary();
                break;
            case 'option1':
                this.executeOption1();
                break;
            case 'option2':
                this.executeOption2();
                break;
            case 'option3':
                this.executeOption3();
                break;
            default:
                console.log('Ação não reconhecida:', action);
        }
    }
    
    executeOption1() {
        console.log('Executando Opção 1');
        // Implementar funcionalidade da Opção 1
        alert('Opção 1 selecionada');
    }
    
    executeOption2() {
        console.log('Executando Opção 2');
        // Implementar funcionalidade da Opção 2
        alert('Opção 2 selecionada');
    }
    
    executeOption3() {
        console.log('Executando Opção 3');
        // Implementar funcionalidade da Opção 3
        alert('Opção 3 selecionada');
    }
    
    // Método para redefinir posição do menu primário
    resetPrimaryPosition() {
        this.primaryMenu.style.left = '';
        this.primaryMenu.style.top = '';
        this.primaryMenu.style.transform = 'translate(-50%, -50%)';
    }
}

// Inicializar quando o DOM estiver carregado
document.addEventListener('DOMContentLoaded', () => {
    window.menuInterface = new MenuInterface();
    
    // Adicionar tecla ESC para voltar ao menu primário
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (!window.menuInterface.secondaryMenu.classList.contains('hidden')) {
                window.menuInterface.switchToPrimary();
            }
        }
    });
    
    // Prevenir menu de contexto padrão do navegador
    document.addEventListener('contextmenu', (e) => {
        if (e.target.closest('#primary-icon')) {
            e.preventDefault();
        }
    });
});