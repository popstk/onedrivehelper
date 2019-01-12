package main

import (
	"log"
	"net/url"
	"time"

	"github.com/gorilla/websocket"
	"github.com/zyxar/argo/rpc"
)

type notifyRequest struct {
	Version string      `json:"jsonrpc"`
	Method  string      `json:"method"`
	Params  []rpc.Event `json:"params"`
}

func doMethod(n rpc.Notifier, request *notifyRequest) {
	switch request.Method {
	case "aria2.onDownloadStart":
		n.OnStart(request.Params)
	case "aria2.onDownloadPause":
		n.OnPause(request.Params)
	case "aria2.onDownloadStop":
		n.OnStop(request.Params)
	case "aria2.onDownloadComplete":
		n.OnComplete(request.Params)
	case "aria2.onDownloadError":
		n.OnError(request.Params)
	case "aria2.onBtDownloadComplete":
		n.OnBtComplete(request.Params)
	default:
		log.Printf("unexpected notification: %s\n", request.Method)
	}
}

func pinger(ws *websocket.Conn, ch chan struct{}) {
	defer ws.Close()
	ticker := time.NewTicker(10 * time.Minute)

	log.Print("pinger")

	for {
		select {
		case <-ticker.C:
			log.Print("Send Ping")
			ws.SetWriteDeadline(time.Now().Add(2 * time.Second))
			if err := ws.WriteMessage(websocket.PingMessage, []byte("ruok")); err != nil {
				log.Print(err)
				return
			}
		case <-ch:
			return
		}
	}
}

func setNotifier(u string, n rpc.Notifier, chexit chan struct{}) error {
	uri, err := url.Parse(u)
	if err != nil {
		return err
	}

	uri.Scheme = "ws"
	ws, _, err := websocket.DefaultDialer.Dial(uri.String(), nil)
	if err != nil {
		return err
	}

	log.Print(uri.String())

	ws.SetCloseHandler(func(code int, text string) error {
		log.Print("closing code = ", code)
		log.Print("closing text = ", text)
		return nil
	})

	ws.SetPongHandler(func(d string) error {
		log.Print("Pong: ", d)
		return nil
	})

	ws.SetPingHandler(func(d string) error {
		log.Print("Ping: ", d)
		return nil
	})

	go func() {
		defer func() {
			ws.Close()
			log.Print("Exit")
		}()

		for {
			log.Print("ReadJSON...")
			var request notifyRequest
			if err := ws.ReadJSON(&request); err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway) {
					log.Print("error:", err)
				}
				return
			}
			doMethod(n, &request)
		}
	}()
	return err
}
