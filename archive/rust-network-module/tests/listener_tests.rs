#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::sync::{mpsc, oneshot};
    use tokio::time::timeout;

    async fn bind() -> TcpListener {
        TcpListener::bind("127.0.0.1:0").await.unwrap()
    }

    #[tokio::test]
    async fn serves_request_and_stops_accepting() {
        timeout(Duration::from_secs(3), async {
            let listener = bind().await;
            let addr = listener.local_addr().unwrap();
            let (stop, stopped) = oneshot::channel();
            let server = tokio::spawn(run_example(listener, async { let _ = stopped.await; },
                2, Duration::from_secs(1), |mut stream| async move {
                    let byte = stream.read_u8().await?;
                    stream.write_u8(byte + 1).await
                }));
            let mut client = TcpStream::connect(addr).await.unwrap();
            client.write_u8(41).await.unwrap();
            assert_eq!(client.read_u8().await.unwrap(), 42);
            stop.send(()).unwrap();
            server.await.unwrap().unwrap();
            assert!(TcpStream::connect(addr).await.is_err());
        }).await.unwrap();
    }

    #[tokio::test]
    async fn connection_error_does_not_kill_listener() {
        timeout(Duration::from_secs(3), async {
            let listener = bind().await;
            let addr = listener.local_addr().unwrap();
            let (stop, stopped) = oneshot::channel();
            let server = tokio::spawn(run_example(listener, async { let _ = stopped.await; },
                1, Duration::from_secs(1), |mut stream| async move {
                    let byte = stream.read_u8().await?;
                    if byte == 0 { return Err(io::Error::new(io::ErrorKind::InvalidData, "bad client")); }
                    stream.write_u8(byte).await
                }));
            let mut bad = TcpStream::connect(addr).await.unwrap();
            bad.write_u8(0).await.unwrap();
            assert!(bad.read_u8().await.is_err());
            let mut good = TcpStream::connect(addr).await.unwrap();
            good.write_u8(42).await.unwrap();
            assert_eq!(good.read_u8().await.unwrap(), 42);
            stop.send(()).unwrap();
            server.await.unwrap().unwrap();
        }).await.unwrap();
    }

    #[tokio::test]
    async fn shutdown_drains_an_active_handler() {
        timeout(Duration::from_secs(3), async {
            let listener = bind().await;
            let addr = listener.local_addr().unwrap();
            let (started, mut starts) = mpsc::unbounded_channel();
            let (stop, stopped) = oneshot::channel();
            let server = tokio::spawn(run_example(listener, async { let _ = stopped.await; },
                1, Duration::from_secs(1), move |mut stream| {
                    let started = started.clone();
                    async move {
                        started.send(()).unwrap();
                        let byte = stream.read_u8().await?;
                        stream.write_u8(byte).await
                    }
                }));
            let mut client = TcpStream::connect(addr).await.unwrap();
            starts.recv().await.unwrap();
            stop.send(()).unwrap();
            tokio::task::yield_now().await;
            client.write_u8(7).await.unwrap();
            assert_eq!(client.read_u8().await.unwrap(), 7);
            server.await.unwrap().unwrap();
        }).await.unwrap();
    }

    struct Active(Arc<AtomicUsize>);
    impl Drop for Active {
        fn drop(&mut self) { self.0.fetch_sub(1, Ordering::SeqCst); }
    }

    #[tokio::test]
    async fn bounds_concurrency_and_aborts_stalled_handlers() {
        timeout(Duration::from_secs(3), async {
            let listener = bind().await;
            let addr = listener.local_addr().unwrap();
            let active = Arc::new(AtomicUsize::new(0));
            let observed = Arc::clone(&active);
            let (started, mut starts) = mpsc::unbounded_channel();
            let (stop, stopped) = oneshot::channel();
            let server = tokio::spawn(run_example(listener, async { let _ = stopped.await; },
                1, Duration::from_millis(20), move |mut stream| {
                    let active = Arc::clone(&active);
                    let started = started.clone();
                    async move {
                        active.fetch_add(1, Ordering::SeqCst);
                        let _guard = Active(active);
                        started.send(()).unwrap();
                        stream.read_u8().await?;
                        Ok(())
                    }
                }));
            let mut first = TcpStream::connect(addr).await.unwrap();
            starts.recv().await.unwrap();
            let _second = TcpStream::connect(addr).await.unwrap();
            assert!(timeout(Duration::from_millis(30), starts.recv()).await.is_err());
            assert_eq!(observed.load(Ordering::SeqCst), 1);
            stop.send(()).unwrap();
            server.await.unwrap().unwrap();
            assert_eq!(observed.load(Ordering::SeqCst), 0);
            assert!(first.read_u8().await.is_err());
        }).await.unwrap();
    }

    #[tokio::test]
    async fn handler_panic_is_observed_as_server_failure() {
        timeout(Duration::from_secs(3), async {
            let listener = bind().await;
            let addr = listener.local_addr().unwrap();
            let server = tokio::spawn(run_example(listener, std::future::pending(),
                1, Duration::from_millis(20), |_stream| async { panic!("test handler panic") }));
            let _client = TcpStream::connect(addr).await.unwrap();
            let err = server.await.unwrap().unwrap_err();
            assert_eq!(err.kind(), io::ErrorKind::Other);
        }).await.unwrap();
    }

    #[tokio::test]
    async fn rejects_zero_capacity_and_handles_immediate_shutdown() {
        let error = run_example(bind().await, async {}, 0, Duration::from_millis(1),
            |_stream| async { Ok(()) }).await.unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
        timeout(Duration::from_secs(1), run_example(bind().await, async {}, 1,
            Duration::from_millis(1), |_stream| async { Ok(()) })).await.unwrap().unwrap();
    }
}
