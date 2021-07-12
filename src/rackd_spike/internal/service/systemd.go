package service

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strconv"
	"sync"

	"github.com/coreos/go-systemd/v22/dbus"
)

const (
	startFailMode = "fail"
	// TODO add more supported start modes
)

const (
	resultDone       = "done"
	resultCanceled   = "canceled"
	resultTimeout    = "timeout"
	resultFailed     = "failed"
	resultIsolate    = "isolate"
	resultIgnoreDeps = "ignore-dependencies"
	resultIgnoreReqs = "ignore-requirements"
)

var (
	systemdConnOnce  = &sync.Once{}
	systemdCloseOnce = &sync.Once{}
)

var (
	ErrSystemdStart           = errors.New("error starting systemd unit")
	ErrSystemdStop            = errors.New("error stopping systemd unit")
	ErrSystemdPIDNotFound     = errors.New("error looking up unit's pid in systemd")
	ErrSystemdInvalidPropType = errors.New("error systemd property not of supported type")
	ErrSystemdServiceNotFound = errors.New("error systemd service not found")
	ErrSystemdBadServiceState = errors.New("error systemd service is not active")
)

var (
	dbusConn *dbus.Conn
)

// getDBusConn will instantiate a connection with dbus based on the current uid
// this happens once and all subsequent calls return the existing connection
func getDBusConn(ctx context.Context) (*dbus.Conn, error) {
	var err error
	systemdConnOnce.Do(func() {
		if os.Getuid() == 0 {
			dbusConn, err = dbus.NewSystemConnectionContext(ctx)
			if err != nil {
				return
			}
		} else {
			dbusConn, err = dbus.NewUserConnectionContext(ctx)
			if err != nil {
				return
			}
		}
	})
	return dbusConn, err
}

// CloseSystemdConn will close the dbus connection to systemd
func CloseSystemdConn() {
	systemdCloseOnce.Do(func() {
		dbusConn.Close()
	})
}

// SystemdService us a service for processes managed by systemd
type SystemdService struct {
	sync.RWMutex
	conn     *dbus.Conn
	name     string
	t        int
	pid      int
	UnitFile string
}

func NewSystemdService(ctx context.Context, name string, t int, unitFile string) (ReloadableService, error) {
	conn, err := getDBusConn(ctx)
	if err != nil {
		return nil, err
	}
	return &SystemdService{
		conn:     conn,
		name:     name,
		t:        t,
		UnitFile: unitFile,
	}, nil
}

func (s *SystemdService) Name() string {
	return s.name
}

func (s *SystemdService) Type() int {
	return s.t
}

func (s *SystemdService) PID() int {
	s.RLock()
	defer s.RUnlock()
	return s.pid
}

func (s *SystemdService) readPIDFromProps(ctx context.Context) error {
	s.Lock()
	defer s.Unlock()
	props, err := s.conn.GetAllPropertiesContext(ctx, s.UnitFile)
	if err != nil {
		return err
	}
	if p, ok := props["ExecMainPID"]; ok {
		switch pid := p.(type) {
		case int:
			s.pid = pid
		case int32:
			s.pid = int(pid)
		case int64:
			s.pid = int(pid)
		case float32:
			s.pid = int(pid)
		case float64:
			s.pid = int(pid)
		case string:
			s.pid, err = strconv.Atoi(pid)
			if err != nil {
				s.pid = -1
				return err
			}
		default:
			return fmt.Errorf("%w: ExecMainPID", ErrSystemdInvalidPropType)
		}
		return nil
	}
	return ErrSystemdPIDNotFound
}

func (s *SystemdService) Start(ctx context.Context) error {
	// "fail" mode will error if process is already running or queued to run
	_, err := s.conn.StartUnitContext(ctx, s.UnitFile, startFailMode, nil)
	if err != nil {
		return err
	}
	return s.readPIDFromProps(ctx)
}

func (s *SystemdService) Stop(ctx context.Context) error {
	_, err := s.conn.StopUnitContext(ctx, s.UnitFile, startFailMode, nil)
	if err != nil {
		return err
	}
	s.Lock()
	defer s.Unlock()
	s.pid = -1
	return nil
}

func (s *SystemdService) Restart(ctx context.Context) error {
	_, err := s.conn.RestartUnitContext(ctx, s.UnitFile, startFailMode, nil)
	if err != nil {
		return err
	}
	return s.readPIDFromProps(ctx)
}

func (s *SystemdService) Status(ctx context.Context) error {
	status, err := s.conn.ListUnitsByNamesContext(ctx, []string{s.UnitFile})
	if err != nil {
		return err
	}
	if len(status) == 0 {
		return fmt.Errorf("%w: %s", ErrSystemdServiceNotFound, s.UnitFile)
	}
	if status[0].ActiveState == "active" || status[0].ActiveState == "running" {
		return nil
	}
	return ErrSystemdBadServiceState
}

func (s *SystemdService) Reload(ctx context.Context) error {
	_, err := s.conn.RestartUnitContext(ctx, s.UnitFile, startFailMode, nil)
	if err != nil {
		return err
	}
	return s.readPIDFromProps(ctx)
}
