var hls;
var debug;
var recoverDecodingErrorDate, recoverSwapAudioCodecDate;
var pendingTimedMetadata = [];

function handleMediaError(hls) {
  var now = performance.now();
  if (!recoverDecodingErrorDate || (now - recoverDecodingErrorDate) > 3000) {
    recoverDecodingErrorDate = performance.now();
    var msg = "trying to recover from media Error ...";
    console.warn(msg);
    hls.recoverMediaError();
  } else if (!recoverSwapAudioCodecDate || (now - recoverSwapAudioCodecDate) > 3000) {
    recoverSwapAudioCodecDate = performance.now();
    var msg = "trying to swap Audio Codec and recover from media Error ...";
    console.warn(msg);
    hls.swapAudioCodec();
    hls.recoverMediaError();
  } else {
    var msg = "cannot recover, last media error recovery failed ...";
    console.error(msg);
  }
}

function handleTimedMetadata(event, data) {
  for (var i = 0; i < data.samples.length; i++) {
    var pts = data.samples[i].pts;
    var str = new TextDecoder('utf-8').decode(data.samples[i].data.subarray(22));
    pendingTimedMetadata.push({ pts: pts, value: str });
  }
}

function timeUpdateCallback() {
  if (pendingTimedMetadata.length == 0 || pendingTimedMetadata[0].pts > video.currentTime) {
    return;
  }
  var e = pendingTimedMetadata.shift(); // Use shift to remove the first element
  console.log('Metadata ' + e.value + " at " + e.pts + "s");
}

function playM3u8(url) {
  var video = document.getElementById('video');
  if (native) {
    video.classList.add("native_mode");
    video.classList.remove("zoomed_mode");
  } else {
    video.classList.remove("native_mode");
    video.classList.add("zoomed_mode");
  }
  if (hls) { hls.destroy(); }
  hls = new Hls({ debug: debug });

  // Use CORS Proxy
  var corsProxy = 'https://corsproxy.io/?'; // Specify the CORS proxy URL
  var m3u8Url = decodeURIComponent(url);
  var proxiedUrl = corsProxy + m3u8Url; // Prepend the proxy URL to the actual URL

  hls.loadSource(proxiedUrl); // Use the proxied URL for the request
  hls.attachMedia(video);
  video.ontimeupdate = timeUpdateCallback;
  hls.on(Hls.Events.MANIFEST_PARSED, function() {
    video.play();
  });
  hls.on(Hls.Events.FRAG_PARSING_METADATA, handleTimedMetadata);
  var chan = 'ABC';
  document.title = chan;
}

debug = false;
var native = false;
var s = document.createElement('script');
s.src = 'https://cdn.jsdelivr.net/npm/hls.js@latest';
s.onload = function() { playM3u8(window.location.href.split("#")[1]); };
(document.head || document.documentElement).appendChild(s);

$(window).bind('hashchange', function() {
  playM3u8(window.location.href.split("#")[1]);
});
