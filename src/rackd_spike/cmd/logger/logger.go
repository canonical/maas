package logger

import (
	"context"
	"io"
	"log/syslog"
	"os"
	"sync"

	"github.com/rs/zerolog"
)

const (
	LoggerJSON = iota
	LoggerConsole
)

const (
	LogPrefix = "rackd"
)

var (
	logger zerolog.Logger
)

var (
	once = &sync.Once{}
)

// New is a helper constructor for creating a singleton root zerolog logger
func New(ctx context.Context, doSyslog bool, level, file string) (context.Context, zerolog.Logger, error) {
	var err error
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	once.Do(func() {
		if doSyslog {
			var syslogger *syslog.Writer
			syslogger, err = syslog.New(syslog.LOG_DAEMON, LogPrefix)
			if err != nil {
				return
			}
			logger = zerolog.New(syslogger)
		} else if len(file) > 0 {
			var f io.WriteCloser
			f, err = os.OpenFile(file, os.O_CREATE|os.O_APPEND, 0644)
			if err != nil {
				return
			}
			go func() {
				<-ctx.Done()
				f.Close()
			}()
			logger = zerolog.New(f)
		} else {
			logger = zerolog.New(os.Stdout)
		}
		logger.WithContext(ctx)
		var logLevel zerolog.Level
		logLevel, err = zerolog.ParseLevel(level)
		if err != nil {
			return
		}
		logger = logger.Level(logLevel)
	})
	return ctx, logger, err
}
