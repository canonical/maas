package logger

import (
	"context"
	"io"
	"log/syslog"
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
	sink   io.Writer
)

var (
	once = &sync.Once{}
)

// New is a helper constructor for creating a singleton root zerolog logger
func New(ctx context.Context, doSyslog bool, file string) (context.Context, *zerolog.Logger, error) {
	var err error
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	once.Do(func() {
		if doSyslog {
			var syslogger *syslog.Writer
			syslogger, err = syslog.New(syslog.LOG_DAEMON, LogPrefix)
			if err != nil {
				return
			}
			sink = zerolog.SyslogLevelWriter(syslogger)
		} else if len(file) > 0 {
			var f io.WriteCloser
			f, err = NewFileSink(file)
			if err != nil {
				return
			}
			go func() {
				<-ctx.Done()
				f.Close()
			}()
			sink = f
		} else {
			sink = zerolog.NewConsoleWriter()
		}
		logger = zerolog.New(sink).With().Timestamp().Logger()
		ctx = logger.WithContext(ctx)
	})
	return ctx, &logger, err
}

func SetLogLevel(logger *zerolog.Logger, level string, debug bool) (*zerolog.Logger, error) {
	if debug {
		level = "debug"
	}

	logLevel, err := zerolog.ParseLevel(level)
	if err != nil {
		return logger, err
	}

	*logger = logger.Level(logLevel)
	return logger, nil
}

func ReOpen() error {
	if r, ok := sink.(ReOpener); ok {
		return r.Reopen()
	}
	return nil
}
