// Ensure video variable is accessible globally if it's used across multiple functions
const video = document.getElementById('video');

// Function to toggle subtitles
function toggleSubtitles() {
    const tracks = video.textTracks;
    for (let i = 0; i < tracks.length; i++) {
        if (tracks[i].kind === 'subtitles') {
            tracks[i].mode = tracks[i].mode === 'showing' ? 'disabled' : 'showing';
        }
    }
}

// Add event listener for context menu button press on the video element
video.addEventListener('contextmenu', function(event) {
    event.preventDefault(); // Prevent default context menu behavior
    toggleSubtitles(); // Toggle subtitles
});
video.addEventListener('loadedmetadata', function() {
    const tracks = video.textTracks;
    for (let i = 0; i < tracks.length; i++) {
        if (tracks[i].kind === 'subtitles') {
            tracks[i].mode = 'hidden';
        }
    }
});
// Function to toggle video description visibility
function toggleVideoDescription() {
    const videoDescription = document.getElementById('video-description');
    videoDescription.style.display = videoDescription.style.display === 'none' || videoDescription.style.display === '' ? 'block' : 'none';
}

// Function to toggle mute and manage subtitles based on mute state
function toggleMuteAndSubtitles() {
    video.muted = !video.muted;
    const tracks = video.textTracks;
    for (let i = 0; i < tracks.length; i++) {
        if (tracks[i].kind === 'subtitles') {
            tracks[i].mode = video.muted ? 'showing' : 'hidden';
            break; // Assuming only one subtitles track is relevant
        }
    }
}

// Add keydown event listener to window
window.addEventListener('keydown', function(event) {
    switch (event.key) {
        case 'Enter':
            video.play();
            break;
        case 'Escape':
        case 'ArrowLeft' && event.metaKey:
            event.preventDefault(); // Prevent default action associated with Escape key
            window.location.href = 'https://goddardduncan.github.io/epg/';
            break;
        case 'ArrowLeft':
            localStorage.setItem('selectedChannel', "mjh-c31"); // Update storedChannel in localStorage
            window.location.href = "http://goddardduncan.github.io/epg/Playm3u8.html?url=https://i.mjh.nz/c31.m3u8";
            break;
        case 'ArrowRight':
            localStorage.setItem('selectedChannel', "mjh-seven-mel"); // Update storedChannel in localStorage
            window.location.href = "http://goddardduncan.github.io/epg/Playm3u8.html?url=https://i.mjh.nz/seven-mel.m3u8";
            break;
        case 'ArrowUp':
            toggleVideoDescription();
            break;
        case 'ArrowDown':
            toggleMuteAndSubtitles();
            break;
    }
});

// Fetch and parse XML data on DOMContentLoaded
document.addEventListener("DOMContentLoaded", function() {
    const xmlData = "https://i.mjh.nz/au/Melbourne/epg.xml";
    selectedChannelId = "mjh-abc-vic";

    if (selectedChannelId) {
        fetch(xmlData)
            .then(response => response.text())
            .then(str => new window.DOMParser().parseFromString(str, "text/xml"))
            .then(data => {
                const currentTime = new Date();
                const timezoneOffsetInMinutes = currentTime.getTimezoneOffset();
                currentTime.setTime(currentTime.getTime() + (timezoneOffsetInMinutes * 60 * 1000));
                const programmes = data.getElementsByTagName("programme");

                for (let program of programmes) {
                    if (program.getAttribute("channel") === selectedChannelId) {
                        const start = new Date(program.getAttribute("start").replace(" +0000", "").replace(/(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/, "$1-$2-$3T$4:$5:$6"));
                        const end = new Date(program.getAttribute("stop").replace(" +0000", "").replace(/(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/, "$1-$2-$3T$4:$5:$6"));

                        if (currentTime >= start && currentTime <= end) {
                            const descElements = program.getElementsByTagName("desc");
                            const desc = descElements.length > 0 ? descElements[0].textContent : 'No description available';
                            localStorage.setItem('descripto', desc);
                            document.getElementById('video-description').textContent = desc;
                            break;
                        }
                    }
                }
            })
            .catch(error => console.error('Error fetching or parsing XML:', error));
    } else {
        console.log("No selected channel found in localStorage.");
    }
});
