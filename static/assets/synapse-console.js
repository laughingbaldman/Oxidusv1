(function () {
    'use strict';

    function classifyStatusText(text) {
        const value = (text || '').toLowerCase();
        if (!value) {
            return 'synapse-state-idle';
        }
        if (/(error|failed|offline|down|unavailable|alert|critical|stalled|unsafe|denied)/.test(value)) {
            return 'synapse-state-critical';
        }
        if (/(running|ready|ok|online|active|enabled|healthy|hybrid|on|connected|started|complete)/.test(value)) {
            return 'synapse-state-active';
        }
        return 'synapse-state-idle';
    }

    function applyStatusClasses() {
        const statusNodes = document.querySelectorAll('.status-item, .status-line');
        statusNodes.forEach((node) => {
            node.classList.remove('synapse-state-active', 'synapse-state-idle', 'synapse-state-critical');
            node.classList.add(classifyStatusText(node.textContent));
        });
    }

    function injectSynapseBackground() {
        if (document.querySelector('.synapse-background')) {
            return;
        }
        const bg = document.createElement('div');
        bg.className = 'synapse-background';
        bg.setAttribute('aria-hidden', 'true');
        document.body.insertBefore(bg, document.body.firstChild);
    }

    function markVisualWrappers() {
        document.querySelectorAll('.left-rail').forEach((el) => el.classList.add('neural-trunk-sidebar'));
        document.querySelectorAll('.forge-nav, .admin-subnav').forEach((el) => el.classList.add('node-cluster-tabs'));
        document.querySelectorAll('.status-item, .status-line').forEach((el) => el.classList.add('synapse-status-dot'));
        document.querySelectorAll('.conversation, .maintenance-output, #knowledgePanel, #thoughtsPanel, #conversationLog, #telemetryOutput').forEach((el) => {
            if (el) {
                el.classList.add('signal-lane-log');
            }
        });
        document.querySelectorAll('.panel').forEach((el) => el.classList.add('glass-panel'));
    }

    function initializeSynapseConsole() {
        document.body.classList.add('synapse-console');
        injectSynapseBackground();
        markVisualWrappers();
        applyStatusClasses();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeSynapseConsole);
    } else {
        initializeSynapseConsole();
    }

    const observer = new MutationObserver(function () {
        markVisualWrappers();
        applyStatusClasses();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
    });
})();
