package main

import (
	"encoding/json"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strconv"

	"github.com/go-redis/redis"
)

const (
	fileName = "config.json"
)

type config struct {
	URL string `json:"url"`
}

func basePath() (string, error) {
	return filepath.Abs(filepath.Dir(os.Args[0]))
}

func parseRedisConf(name string) (string, error) {
	data, err := ioutil.ReadFile(name)
	if err != nil {
		return "", err
	}
	var conf config
	err = json.Unmarshal(data, &conf)
	if err != nil {
		return "", err
	}

	return conf.URL, nil
}

func main() {
	if len(os.Args) < 4 {
		log.Print("too few arguments")
		return
	}

	count, err := strconv.ParseUint(os.Args[2], 10, 64)
	if err != nil {
		log.Print(err)
		return
	}

	if count == 0 {
		return
	}

	base, err := basePath()
	if err != nil {
		log.Print(err)
		return
	}

	u, err := parseRedisConf(filepath.Join(base, fileName))
	if err != nil {
		log.Print(err)
		return
	}
	opt, err := redis.ParseURL(u)
	if err != nil {
		log.Print(err)
		return
	}
	client := redis.NewClient(opt)
	_, err = client.RPush("upload", os.Args[3]).Result()
	if err != nil {
		log.Print(err)
		return
	}
}
