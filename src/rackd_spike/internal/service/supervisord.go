package service

import (
	"context"
	"errors"
	"fmt"
	"net/rpc"
	"strconv"
	"sync"

	"github.com/kolo/xmlrpc"
)

var (
	xmlrpcConnOnce  = &sync.Once{}
	xmlrpcCloseOnce = &sync.Once{}
)

var (
	supConn *xmlrpc.Client
)

var (
	ErrSupervisordPIDNotFound     = errors.New("error supervisord service pid not found")
	ErrSupervisordUnsupportedType = errors.New("received an unsupported type from supervisord")
)

// getSupervisordConn will get a connection to supervisord's rpc interface, instantiated once and can be returned multiple times
func getSupervisordConn(endpoint string) (*xmlrpc.Client, error) {
	var err error
	xmlrpcConnOnce.Do(func() {
		supConn, err = xmlrpc.NewClient(endpoint, nil)
	})
	return supConn, err
}

// CloseSupervisordConn will close the connection to the supervisord rpc interface
func CloseSupervisordConn() error {
	var err error
	xmlrpcCloseOnce.Do(func() {
		err = supConn.Close()
	})
	return err
}

// SupervisordService is a service managed by supervisord
type SupervisordService struct {
	sync.RWMutex
	conn *xmlrpc.Client
	name string
	pid  int
	t    int
}

func NewSupervisordService(endpoint, name string, t int) (Service, error) {
	conn, err := getSupervisordConn(endpoint)
	if err != nil {
		return nil, err
	}
	return &SupervisordService{
		conn: conn,
		name: name,
		t:    t,
	}, nil
}

func (s *SupervisordService) Name() string {
	return s.name
}

func (s *SupervisordService) Type() int {
	return s.t
}

func (s *SupervisordService) PID() int {
	s.RLock()
	defer s.RUnlock()
	return s.pid
}

func (s *SupervisordService) readPIDFromResult(res map[string]interface{}) error {
	if pidField, ok := res["pid"]; ok {
		s.Lock()
		defer s.Unlock()
		var err error
		switch pid := pidField.(type) {
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
			return fmt.Errorf("%w: pid:%v", ErrSupervisordUnsupportedType, pid)
		}
		return nil
	}
	return ErrSupervisordPIDNotFound
}

func (s *SupervisordService) Start(ctx context.Context) error {
	resChan := make(chan *rpc.Call)
	s.conn.Go("startProcess", []interface{}{s.name}, nil, resChan)
	select {
	case <-ctx.Done():
		return ctx.Err()
	case call := <-resChan:
		if call.Error != nil {
			return call.Error
		}
		res, err := s.getProcInfo(ctx)
		if err != nil {
			return err
		}
		err = s.readPIDFromResult(res)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *SupervisordService) Stop(ctx context.Context) error {
	resChan := make(chan *rpc.Call)
	s.conn.Go("stopProcess", []interface{}{s.name}, nil, resChan)
	select {
	case <-ctx.Done():
		return ctx.Err()
	case call := <-resChan:
		if call.Error != nil {
			return call.Error
		}
		s.Lock()
		defer s.Unlock()
		s.pid = -1
	}
	return nil
}

func (s *SupervisordService) Restart(ctx context.Context) error {
	err := s.Stop(ctx)
	if err != nil {
		return err
	}
	return s.Start(ctx)
}

func (s *SupervisordService) getProcInfo(ctx context.Context) (map[string]interface{}, error) {
	resChan := make(chan *rpc.Call)
	s.conn.Go("getProcessInfo", []interface{}{s.name}, nil, resChan)
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case call := <-resChan:
		if call.Error != nil {
			return nil, call.Error
		}
		res, ok := call.Reply.(map[string]interface{})
		if !ok {
			return nil, ErrSupervisordUnsupportedType
		}
		return res, nil
	}
}

func (s *SupervisordService) Status(ctx context.Context) error {
	info, err := s.getProcInfo(ctx)
	if err != nil {
		return err
	}
	if info["stop"] != 0 {
		return fmt.Errorf("%w: service %s exited", ErrUnexpectedServiceExit, s.name)
	}
	return nil
}
