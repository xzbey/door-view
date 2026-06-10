function loadStream() {
    const video = document.getElementById('video');
    const status = document.getElementById('status');
    const src = '/stream/stream.m3u8';

    if (Hls.isSupported()) { // все браузеры, кроме Safari, поддерживают HLS через библиотеку hls.js
        const hls = new Hls({
            liveSyncDurationCount: 3,
            liveMaxLatencyDurationCount: 5,
        });
        hls.loadSource(src);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
            status.textContent = 'онлайн';
            video.play();
        });
        hls.on(Hls.Events.ERROR, (event, data) => {
            if (data.fatal) {
                status.textContent = 'ошибка стрима, переподключение...';
                setTimeout(() => hls.loadSource(src), 3000);
            }
        });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) { // Safari подднерживает HLS нативно
        video.src = src;
        video.addEventListener('loadedmetadata', () => {
            status.textContent = 'онлайн';
            video.play();
        });
    } else { // пизда
        status.textContent = 'браузер не поддерживает HLS';
    }
}