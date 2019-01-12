package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/go-redis/redis"
	"github.com/zyxar/argo/rpc"
)

const (
	fileName = "config.json"
)

type config struct {
	URL    string `json:"url"`
	Queue  string `json:"queue"`
	RPC    string `json:"rpc"`
	Secret string `json:"secret"`
}

type notifier struct {
	rpc.DummyNotifier
	rpcClient   rpc.Protocol
	redisClient *redis.Client
}

var conf config

func init() {
	log.SetFlags(log.Lshortfile | log.Ltime)

	var err error
	conf, err = parseConf(fileName)
	if err != nil {
		log.Panic(err)
	}
}

func basePath() (string, error) {
	return filepath.Abs(filepath.Dir(os.Args[0]))
}

func parseConf(name string) (config, error) {
	var conf config
	data, err := ioutil.ReadFile(name)
	if err != nil {
		return conf, err
	}

	err = json.Unmarshal(data, &conf)
	if err != nil {
		return conf, err
	}
	return conf, nil
}

func formatPath(dir, path string) (string, error) {
	if dir == "" {
		return "", errors.New("Empty directory")
	}

	if !strings.HasPrefix(path, dir) {
		return "", errors.New("Invalid dir and path")
	}

	f, err := os.Stat(path)
	if os.IsNotExist(err) {
		return "", errors.New(fmt.Sprint("Not exist file: ", path))
	}
	if f.IsDir() {
		return "", errors.New(fmt.Sprint("Not file: ", path))
	}

	path = path[len(dir):]
	parts := strings.Split(path, string(filepath.Separator))
	if len(parts) == 0 {
		return "", errors.New(fmt.Sprint("Invalid path: ", path))
	}

	return filepath.Join(dir, parts[0]), nil
}

func (d *notifier) OnComplete(es []rpc.Event) {
	for _, e := range es {
		log.Print("Complete gid = ", e.Gid)
		status, err := d.rpcClient.TellStatus(e.Gid, "dir", "files")
		if err != nil {
			log.Print(err)
			continue
		}

		log.Print("Download path is ", status.Dir)
		if len(status.Files) == 0 {
			log.Print("Empty: ", e.Gid)
			continue
		}

		path, err := formatPath(status.Dir, status.Files[0].Path)
		if err != nil {
			log.Print(err)
			continue
		}

		log.Print("Enqueue path: ", path)
		_, err = d.redisClient.RPush(conf.Queue, path).Result()
		if err != nil {
			log.Print(err)
			continue
		}
	}
}

func main() {
	setupStackTrap()

	opt, err := redis.ParseURL(conf.URL)
	if err != nil {
		log.Panic(err)
	}

	rpcc, err := rpc.New(conf.RPC, conf.Secret)
	if err != nil {
		log.Panic(err)
	}

	notify := &notifier{
		rpcClient:   rpcc,
		redisClient: redis.NewClient(opt),
	}

	chexit := make(chan struct{})
	err = setNotifier(conf.RPC, notify, chexit)
	if err != nil {
		log.Panic(err)
	}

	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGINT, syscall.SIGKILL, syscall.SIGTERM)
	<-ch
}
