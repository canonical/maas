package log

import (
	"github.com/rs/zerolog"
)

// Logger is an adapter that allows usage of zerolog with Temporal Client
type Logger struct {
	logger zerolog.Logger
}

// NewZerologAdapter returns new workflow Logger
// based on zerolog
func NewZerologAdapter(logger zerolog.Logger) *Logger {
	return &Logger{
		logger: logger,
	}
}

// Debug implements Temporal log.Logger interface
func (l *Logger) Debug(msg string, keyvals ...interface{}) {
	sendEvent(l.logger.Debug(), msg, keyvals)
}

// Info implements Temporal log.Logger interface
func (l *Logger) Info(msg string, keyvals ...interface{}) {
	sendEvent(l.logger.Info(), msg, keyvals)
}

// Warn implements Temporal log.Logger interface
func (l *Logger) Warn(msg string, keyvals ...interface{}) {
	sendEvent(l.logger.Warn(), msg, keyvals)
}

// Error implements Temporal log.Logger interface
func (l *Logger) Error(msg string, keyvals ...interface{}) {
	sendEvent(l.logger.Error(), msg, keyvals)
}

func sendEvent(event *zerolog.Event, msg string, keyvals ...interface{}) {
	if len(keyvals) > 0 {
		event.Fields(keyvals[0])
	}

	event.Msg(msg)
}
