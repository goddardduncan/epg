// ==UserScript==
// @name         Sniff 9Now Streams, Format and Open github to append
// @namespace    https://github.com/goddardduncan/epg
// @version      1.4
// @description  Copy the 9Now m3u8 stream URLs, format them for EPG and open github for edits
// @match        https://www.9now.com.au/live/*
// @match        https://www.9now.com.au/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const TOGGLE_KEY = 'sniffAwayToggle';
    let isSniffing = JSON.parse(localStorage.getItem(TOGGLE_KEY)) || false;

    if (window.location.href === 'https://www.9now.com.au/') {
        isSniffing = false;
        localStorage.setItem(TOGGLE_KEY, JSON.stringify(isSniffing));
    }

    const urlsToVisit = [
        'https://www.9now.com.au/live/channel-9',
        'https://www.9now.com.au/live/gem',
        'https://www.9now.com.au/live/go',
        'https://www.9now.com.au/live/life',
        'https://www.9now.com.au/live/rush'
    ];

    const channelIds = {
        'https://www.9now.com.au/live/channel-9': 'mjh-channel-9-vic',
        'https://www.9now.com.au/live/gem': 'mjh-gem-vic',
        'https://www.9now.com.au/live/go': 'mjh-go-vic',
        'https://www.9now.com.au/live/life': 'mjh-life-vic',
        'https://www.9now.com.au/live/rush': 'mjh-rush-vic'
    };

    let clipboardContents = sessionStorage.getItem('clipboardContents') ? JSON.parse(sessionStorage.getItem('clipboardContents')) : {};

    // Function to copy text to clipboard
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            console.log('Stream URL copied to clipboard:', text);
        }).catch(err => {
            console.error('Failed to copy to clipboard:', err);
        });
    }

    // Function to clear clipboard
    function clearClipboard() {
        sessionStorage.removeItem('clipboardContents');
        clipboardContents = {};
        console.log('Clipboard cleared');
    }

    // Function to handle copying the stream URL
    function handleStreamUrl() {
        if (!isSniffing) return;

        const element = document.querySelector('[data-param-live-stream-url]');
        if (element && element.getAttribute('data-param-live-stream-url')) {
            const currentUrl = window.location.href;
            const channelId = channelIds[currentUrl];
            clipboardContents[channelId] = element.getAttribute('data-param-live-stream-url');
            sessionStorage.setItem('clipboardContents', JSON.stringify(clipboardContents));
            navigateToNextUrl();
        }
    }

    // Function to navigate to the next URL in the list
    function navigateToNextUrl() {
        const currentUrl = window.location.href;
        const currentIndex = urlsToVisit.indexOf(currentUrl);

        if (currentIndex > -1 && currentIndex < urlsToVisit.length - 1) {
            const nextUrl = urlsToVisit[currentIndex + 1];
            window.location.href = nextUrl;
        } else {
            console.log('All URLs visited, preparing clipboard.');
            prepareClipboardText();
        }
    }

    // Function to prepare the clipboard text
    function prepareClipboardText() {
        const updatedChannelLinkMap = {
            "mjh-channel-9-vic": clipboardContents['mjh-channel-9-vic'] || "",
            "mjh-gem-vic": clipboardContents['mjh-gem-vic'] || "",
            "mjh-go-vic": clipboardContents['mjh-go-vic'] || "",
            "mjh-life-vic": clipboardContents['mjh-life-vic'] || "",
            "mjh-rush-vic": clipboardContents['mjh-rush-vic'] || ""
        };

        const formattedText = `
            const channelLinkMap = {
                "mjh-channel-9-vic": "${updatedChannelLinkMap['mjh-channel-9-vic']}",
                "mjh-gem-vic": "${updatedChannelLinkMap['mjh-gem-vic']}",
                "mjh-go-vic": "${updatedChannelLinkMap['mjh-go-vic']}",
                "mjh-life-vic": "${updatedChannelLinkMap['mjh-life-vic']}",
                "mjh-rush-vic": "${updatedChannelLinkMap['mjh-rush-vic']}",
                "mjh-seven-mel": "Playm3u8.html?url=https://i.mjh.nz/seven-mel.m3u8",
                "mjh-7two-mel": "Playm3u8.html?url=https://i.mjh.nz/7two-mel.m3u8",
                "mjh-7mate-mel": "Playm3u8.html?url=https://i.mjh.nz/7mate-mel.m3u8",
                "mjh-7flix-mel": "Playm3u8.html?url=https://i.mjh.nz/7flix-mel.m3u8",
                "mjh-abc-vic": "player.html#https://c.mjh.nz/abc-vic.m3u8",
                "mjh-sbs": "Playm3u8.html?url=https://i.mjh.nz/sbs.m3u8",
                "mjh-sbs-vic-hd": "Playm3u8.html?url=https://i.mjh.nz/sbs-vic-hd.m3u8",
                "mjh-sbs-viceland": "Playm3u8.html?url=https://i.mjh.nz/sbs-viceland.m3u8",
                "mjh-sbs-food": "Playm3u8.html?url=https://i.mjh.nz/sbs-food.m3u8",
                "mjh-sbs-world-movies": "Playm3u8.html?url=https://i.mjh.nz/sbs-world-movies.m3u8",
                "mjh-sbs-nitv": "Playm3u8.html?url=https://i.mjh.nz/sbs-nitv.m3u8",
                "mjh-10-vic": "Playm3u8.html?url=https://i.mjh.nz/10-vic.m3u8",
                "mjh-10peach-vic": "Playm3u8.html?url=https://i.mjh.nz/10peach-vic.m3u8",
                "mjh-10bold-vic": "Playm3u8.html?url=https://i.mjh.nz/10bold-vic.m3u8",
                "mjh-10shake-vic": "Playm3u8.html?url=https://i.mjh.nz/10shake-vic.m3u8",
                "mjh-eleven-vic": "Playm3u8.html?url=https://i.mjh.nz/eleven-vic.m3u8",
                "mjh-one-vic": "Playm3u8.html?url=https://i.mjh.nz/one-vic.m3u8",
                "mjh-sky-news-aus": "Playm3u8.html?url=https://i.mjh.nz/sky-news-aus.m3u8",
                "mjh-fox-sports-news": "Playm3u8.html?url=https://i.mjh.nz/fox-sports-news.m3u8",
                "mjh-c31": "Playm3u8.html?url=https://i.mjh.nz/c31.m3u8",
            };
        `;

        copyToClipboard(formattedText);
        turnOffSniffing(); // Turn off sniffing before navigating to GitHub or Channel 9
        navigateAfterSniffing();
    }

    // Function to turn off sniffing and save to localStorage
    function turnOffSniffing() {
        isSniffing = false;
        localStorage.setItem(TOGGLE_KEY, JSON.stringify(isSniffing));
        updateToggleHTML();
    }

    // Function to navigate to the GitHub page or Channel 9
    function navigateAfterSniffing() {
        if (window.location.href === 'https://www.9now.com.au/') {
            window.location.href = 'https://www.9now.com.au/live/channel-9';
        } else {
            window.location.href = 'https://github.com/goddardduncan/epg/edit/main/index.html#173';
        }
    }

    // Create a MutationObserver to watch for changes in the DOM
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                handleStreamUrl();
            }
        }
    });

    // Check if the current URL is https://www.9now.com.au/live/channel-9 and clear clipboard if true
    if (window.location.href === 'https://www.9now.com.au/live/channel-9') {
        clearClipboard();
    }

    // Start observing the body for changes if sniffing is enabled
    if (isSniffing && window.location.href !== 'https://www.9now.com.au/') {
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true
        });

        handleStreamUrl(); // Initial call to handle the stream URL if the element is already present
    }

    // Create the "Sniff Away" toggle switch
    const toggleDiv = document.createElement('div');
    toggleDiv.style.position = 'fixed';
    toggleDiv.style.bottom = '10px';
    toggleDiv.style.left = '10px';
    toggleDiv.style.zIndex = '9999';
    toggleDiv.style.padding = '10px';
    toggleDiv.style.backgroundColor = '#000';
    toggleDiv.style.border = '1px solid #ccc';
    toggleDiv.style.borderRadius = '4px';
    toggleDiv.style.cursor = 'pointer';
    toggleDiv.style.boxShadow = '0 2px 5px rgba(0,0,0,0.1)';
    toggleDiv.style.display = 'flex';
    toggleDiv.style.alignItems = 'center';

    const toggleLabel = document.createElement('label');
    toggleLabel.style.marginLeft = '8px';
    toggleLabel.textContent = 'Sniff Away';
    toggleLabel.style.background = 'linear-gradient(to right, red, orange, yellow, green, blue, indigo, violet)';
    toggleLabel.style.webkitBackgroundClip = 'text';
    toggleLabel.style.webkitTextFillColor = 'transparent';
    toggleLabel.style.fontSize = '14px'; // Adjust the font size here
    toggleDiv.appendChild(toggleLabel);

    const toggleInput = document.createElement('input');
    toggleInput.id = 'sniffAwayToggle';
    toggleInput.type = 'checkbox';
    toggleInput.checked = isSniffing;
    toggleInput.style.display = 'none';
    toggleDiv.appendChild(toggleInput);

    const switchSpan = document.createElement('span');
    switchSpan.style.position = 'relative';
    switchSpan.style.backgroundColor = isSniffing ? '#AD68FF' : '#ccc';
    switchSpan.style.width = '34px';
    switchSpan.style.height = '15px';
    switchSpan.style.transition = '0.4s';
    switchSpan.style.borderRadius = '28px';
    switchSpan.style.display = 'inline-block';
    switchSpan.style.cursor = 'pointer';
    switchSpan.style.marginRight = '5px';
    toggleDiv.appendChild(switchSpan);

    const knobSpan = document.createElement('span');
    knobSpan.style.position = 'absolute';
    knobSpan.style.left = isSniffing ? '3px' : '20px';
    knobSpan.style.bottom = '0.075em';
    knobSpan.style.width = '14px';
    knobSpan.style.height = '13px';
    knobSpan.style.borderRadius = '28px';
    knobSpan.style.backgroundColor = 'white';
    knobSpan.style.transition = '0.4s';
    knobSpan.style.display = 'block';
    knobSpan.style.zIndex = '1';
    switchSpan.appendChild(knobSpan);

    toggleDiv.addEventListener('click', () => {
        isSniffing = !isSniffing;
        localStorage.setItem(TOGGLE_KEY, JSON.stringify(isSniffing));
        updateToggleHTML();

        if (isSniffing) {
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true
            });
            handleStreamUrl();
        } else {
            observer.disconnect();
            if (window.location.href === 'https://www.9now.com.au/') {
                window.location.href = 'https://www.9now.com.au/live/channel-9';
            }
        }
    });

    document.body.appendChild(toggleDiv);

    function updateToggleHTML() {
        toggleInput.checked = isSniffing;
        switchSpan.style.backgroundColor = isSniffing ? '#AD68FF' : '#ccc';
        knobSpan.style.transform = isSniffing ? 'translateX(0)' : 'translateX(15px)';
    }
})();