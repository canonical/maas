package logger

import (
	"log"
	"os"
	"sync"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/diode"
)

const (
	LOG_FILE_MODE  = 0644
	LOG_DROP_LIMIT = 100
)

type ReOpener interface {
	Reopen() error
}

type FileSink struct {
	filename string
	wr       diode.Writer
	lock     sync.RWMutex
}

func NewFileSink(file string) (*FileSink, error) {
	wr, err := open(file)
	if err != nil {
		return nil, err
	}
	return &FileSink{filename: file, wr: wr}, nil
}

func (f *FileSink) Write(p []byte) (n int, err error) {
	f.lock.RLock()
	defer f.lock.RUnlock()
	return f.wr.Write(p)
}

func (f *FileSink) Close() error {
	f.lock.Lock()
	defer f.lock.Unlock()
	return f.wr.Close()
}

func (f *FileSink) WriteLevel(level zerolog.Level, p []byte) (n int, err error) {
	f.lock.RLock()
	defer f.lock.RUnlock()
	return f.wr.Write(p)
}

// Reopen renew file inode
func (f *FileSink) Reopen() error {
	f.lock.Lock()
	defer f.lock.Unlock()

	newWr, err := open(f.filename)
	if err != nil {
		return err
	}

	f.wr.Close()
	f.wr = newWr

	return nil
}

func open(file string) (diode.Writer, error) {
	f, err := os.OpenFile(file, os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		return diode.Writer{}, err
	}
	wr := diode.NewWriter(f, LOG_DROP_LIMIT, 0, func(missed int) {
		log.Printf("Dropped %d messages", missed)
	})
	return wr, err
}
