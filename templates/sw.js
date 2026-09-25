/* Service worker — Web Push receiver. No build step, plain JS. */
self.addEventListener('push', function (event) {
    var data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (e) {
        data = { title: 'Shri Raj Construction', body: (event.data && event.data.text()) || '' };
    }
    var title = data.title || 'Shri Raj Construction';
    var options = {
        body: data.body || '',
        data: { url: data.url || '/labour/' },
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var url = (event.notification.data && event.notification.data.url) || '/labour/';
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].url.indexOf(url) !== -1) {
                    return list[i].focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
