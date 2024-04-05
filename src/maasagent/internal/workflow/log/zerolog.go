// Copyright (c) 2023-2024 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
