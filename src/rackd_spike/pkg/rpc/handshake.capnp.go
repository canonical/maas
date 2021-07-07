// Code generated by capnpc-go. DO NOT EDIT.

package rpc

import (
	capnp "capnproto.org/go/capnp/v3"
	text "capnproto.org/go/capnp/v3/encoding/text"
	schemas "capnproto.org/go/capnp/v3/schemas"
	server "capnproto.org/go/capnp/v3/server"
	context "context"
)

type AuthResponse struct{ capnp.Struct }

// AuthResponse_TypeID is the unique identifier for the type AuthResponse.
const AuthResponse_TypeID = 0x98b03f82d720e4e1

func NewAuthResponse(s *capnp.Segment) (AuthResponse, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 2})
	return AuthResponse{st}, err
}

func NewRootAuthResponse(s *capnp.Segment) (AuthResponse, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 2})
	return AuthResponse{st}, err
}

func ReadRootAuthResponse(msg *capnp.Message) (AuthResponse, error) {
	root, err := msg.Root()
	return AuthResponse{root.Struct()}, err
}

func (s AuthResponse) String() string {
	str, _ := text.Marshal(0x98b03f82d720e4e1, s.Struct)
	return str
}

func (s AuthResponse) Salt() ([]byte, error) {
	p, err := s.Struct.Ptr(0)
	return []byte(p.Data()), err
}

func (s AuthResponse) HasSalt() bool {
	return s.Struct.HasPtr(0)
}

func (s AuthResponse) SetSalt(v []byte) error {
	return s.Struct.SetData(0, v)
}

func (s AuthResponse) Digest() ([]byte, error) {
	p, err := s.Struct.Ptr(1)
	return []byte(p.Data()), err
}

func (s AuthResponse) HasDigest() bool {
	return s.Struct.HasPtr(1)
}

func (s AuthResponse) SetDigest(v []byte) error {
	return s.Struct.SetData(1, v)
}

// AuthResponse_List is a list of AuthResponse.
type AuthResponse_List struct{ capnp.List }

// NewAuthResponse creates a new list of AuthResponse.
func NewAuthResponse_List(s *capnp.Segment, sz int32) (AuthResponse_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 0, PointerCount: 2}, sz)
	return AuthResponse_List{l}, err
}

func (s AuthResponse_List) At(i int) AuthResponse { return AuthResponse{s.List.Struct(i)} }

func (s AuthResponse_List) Set(i int, v AuthResponse) error { return s.List.SetStruct(i, v.Struct) }

func (s AuthResponse_List) String() string {
	str, _ := text.MarshalList(0x98b03f82d720e4e1, s.List)
	return str
}

// AuthResponse_Future is a wrapper for a AuthResponse promised by a client call.
type AuthResponse_Future struct{ *capnp.Future }

func (p AuthResponse_Future) Struct() (AuthResponse, error) {
	s, err := p.Future.Struct()
	return AuthResponse{s}, err
}

type Authenticator struct{ Client *capnp.Client }

// Authenticator_TypeID is the unique identifier for the type Authenticator.
const Authenticator_TypeID = 0x800ae3a77a7bc18e

func (c Authenticator) Authenticate(ctx context.Context, params func(Authenticator_authenticate_Params) error) (Authenticator_authenticate_Results_Future, capnp.ReleaseFunc) {
	s := capnp.Send{
		Method: capnp.Method{
			InterfaceID:   0x800ae3a77a7bc18e,
			MethodID:      0,
			InterfaceName: "handshake.capnp:Authenticator",
			MethodName:    "authenticate",
		},
	}
	if params != nil {
		s.ArgsSize = capnp.ObjectSize{DataSize: 0, PointerCount: 1}
		s.PlaceArgs = func(s capnp.Struct) error { return params(Authenticator_authenticate_Params{Struct: s}) }
	}
	ans, release := c.Client.SendCall(ctx, s)
	return Authenticator_authenticate_Results_Future{Future: ans.Future()}, release
}

func (c Authenticator) AddRef() Authenticator {
	return Authenticator{
		Client: c.Client.AddRef(),
	}
}

func (c Authenticator) Release() {
	c.Client.Release()
}

// A Authenticator_Server is a Authenticator with a local implementation.
type Authenticator_Server interface {
	Authenticate(context.Context, Authenticator_authenticate) error
}

// Authenticator_NewServer creates a new Server from an implementation of Authenticator_Server.
func Authenticator_NewServer(s Authenticator_Server, policy *server.Policy) *server.Server {
	c, _ := s.(server.Shutdowner)
	return server.New(Authenticator_Methods(nil, s), s, c, policy)
}

// Authenticator_ServerToClient creates a new Client from an implementation of Authenticator_Server.
// The caller is responsible for calling Release on the returned Client.
func Authenticator_ServerToClient(s Authenticator_Server, policy *server.Policy) Authenticator {
	return Authenticator{Client: capnp.NewClient(Authenticator_NewServer(s, policy))}
}

// Authenticator_Methods appends Methods to a slice that invoke the methods on s.
// This can be used to create a more complicated Server.
func Authenticator_Methods(methods []server.Method, s Authenticator_Server) []server.Method {
	if cap(methods) == 0 {
		methods = make([]server.Method, 0, 1)
	}

	methods = append(methods, server.Method{
		Method: capnp.Method{
			InterfaceID:   0x800ae3a77a7bc18e,
			MethodID:      0,
			InterfaceName: "handshake.capnp:Authenticator",
			MethodName:    "authenticate",
		},
		Impl: func(ctx context.Context, call *server.Call) error {
			return s.Authenticate(ctx, Authenticator_authenticate{call})
		},
	})

	return methods
}

// Authenticator_authenticate holds the state for a server call to Authenticator.authenticate.
// See server.Call for documentation.
type Authenticator_authenticate struct {
	*server.Call
}

// Args returns the call's arguments.
func (c Authenticator_authenticate) Args() Authenticator_authenticate_Params {
	return Authenticator_authenticate_Params{Struct: c.Call.Args()}
}

// AllocResults allocates the results struct.
func (c Authenticator_authenticate) AllocResults() (Authenticator_authenticate_Results, error) {
	r, err := c.Call.AllocResults(capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Authenticator_authenticate_Results{Struct: r}, err
}

type Authenticator_authenticate_Params struct{ capnp.Struct }

// Authenticator_authenticate_Params_TypeID is the unique identifier for the type Authenticator_authenticate_Params.
const Authenticator_authenticate_Params_TypeID = 0xdbaca3bedaffa653

func NewAuthenticator_authenticate_Params(s *capnp.Segment) (Authenticator_authenticate_Params, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Authenticator_authenticate_Params{st}, err
}

func NewRootAuthenticator_authenticate_Params(s *capnp.Segment) (Authenticator_authenticate_Params, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Authenticator_authenticate_Params{st}, err
}

func ReadRootAuthenticator_authenticate_Params(msg *capnp.Message) (Authenticator_authenticate_Params, error) {
	root, err := msg.Root()
	return Authenticator_authenticate_Params{root.Struct()}, err
}

func (s Authenticator_authenticate_Params) String() string {
	str, _ := text.Marshal(0xdbaca3bedaffa653, s.Struct)
	return str
}

func (s Authenticator_authenticate_Params) Msg() ([]byte, error) {
	p, err := s.Struct.Ptr(0)
	return []byte(p.Data()), err
}

func (s Authenticator_authenticate_Params) HasMsg() bool {
	return s.Struct.HasPtr(0)
}

func (s Authenticator_authenticate_Params) SetMsg(v []byte) error {
	return s.Struct.SetData(0, v)
}

// Authenticator_authenticate_Params_List is a list of Authenticator_authenticate_Params.
type Authenticator_authenticate_Params_List struct{ capnp.List }

// NewAuthenticator_authenticate_Params creates a new list of Authenticator_authenticate_Params.
func NewAuthenticator_authenticate_Params_List(s *capnp.Segment, sz int32) (Authenticator_authenticate_Params_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1}, sz)
	return Authenticator_authenticate_Params_List{l}, err
}

func (s Authenticator_authenticate_Params_List) At(i int) Authenticator_authenticate_Params {
	return Authenticator_authenticate_Params{s.List.Struct(i)}
}

func (s Authenticator_authenticate_Params_List) Set(i int, v Authenticator_authenticate_Params) error {
	return s.List.SetStruct(i, v.Struct)
}

func (s Authenticator_authenticate_Params_List) String() string {
	str, _ := text.MarshalList(0xdbaca3bedaffa653, s.List)
	return str
}

// Authenticator_authenticate_Params_Future is a wrapper for a Authenticator_authenticate_Params promised by a client call.
type Authenticator_authenticate_Params_Future struct{ *capnp.Future }

func (p Authenticator_authenticate_Params_Future) Struct() (Authenticator_authenticate_Params, error) {
	s, err := p.Future.Struct()
	return Authenticator_authenticate_Params{s}, err
}

type Authenticator_authenticate_Results struct{ capnp.Struct }

// Authenticator_authenticate_Results_TypeID is the unique identifier for the type Authenticator_authenticate_Results.
const Authenticator_authenticate_Results_TypeID = 0x96c07ce683897942

func NewAuthenticator_authenticate_Results(s *capnp.Segment) (Authenticator_authenticate_Results, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Authenticator_authenticate_Results{st}, err
}

func NewRootAuthenticator_authenticate_Results(s *capnp.Segment) (Authenticator_authenticate_Results, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Authenticator_authenticate_Results{st}, err
}

func ReadRootAuthenticator_authenticate_Results(msg *capnp.Message) (Authenticator_authenticate_Results, error) {
	root, err := msg.Root()
	return Authenticator_authenticate_Results{root.Struct()}, err
}

func (s Authenticator_authenticate_Results) String() string {
	str, _ := text.Marshal(0x96c07ce683897942, s.Struct)
	return str
}

func (s Authenticator_authenticate_Results) Resp() (AuthResponse, error) {
	p, err := s.Struct.Ptr(0)
	return AuthResponse{Struct: p.Struct()}, err
}

func (s Authenticator_authenticate_Results) HasResp() bool {
	return s.Struct.HasPtr(0)
}

func (s Authenticator_authenticate_Results) SetResp(v AuthResponse) error {
	return s.Struct.SetPtr(0, v.Struct.ToPtr())
}

// NewResp sets the resp field to a newly
// allocated AuthResponse struct, preferring placement in s's segment.
func (s Authenticator_authenticate_Results) NewResp() (AuthResponse, error) {
	ss, err := NewAuthResponse(s.Struct.Segment())
	if err != nil {
		return AuthResponse{}, err
	}
	err = s.Struct.SetPtr(0, ss.Struct.ToPtr())
	return ss, err
}

// Authenticator_authenticate_Results_List is a list of Authenticator_authenticate_Results.
type Authenticator_authenticate_Results_List struct{ capnp.List }

// NewAuthenticator_authenticate_Results creates a new list of Authenticator_authenticate_Results.
func NewAuthenticator_authenticate_Results_List(s *capnp.Segment, sz int32) (Authenticator_authenticate_Results_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1}, sz)
	return Authenticator_authenticate_Results_List{l}, err
}

func (s Authenticator_authenticate_Results_List) At(i int) Authenticator_authenticate_Results {
	return Authenticator_authenticate_Results{s.List.Struct(i)}
}

func (s Authenticator_authenticate_Results_List) Set(i int, v Authenticator_authenticate_Results) error {
	return s.List.SetStruct(i, v.Struct)
}

func (s Authenticator_authenticate_Results_List) String() string {
	str, _ := text.MarshalList(0x96c07ce683897942, s.List)
	return str
}

// Authenticator_authenticate_Results_Future is a wrapper for a Authenticator_authenticate_Results promised by a client call.
type Authenticator_authenticate_Results_Future struct{ *capnp.Future }

func (p Authenticator_authenticate_Results_Future) Struct() (Authenticator_authenticate_Results, error) {
	s, err := p.Future.Struct()
	return Authenticator_authenticate_Results{s}, err
}

func (p Authenticator_authenticate_Results_Future) Resp() AuthResponse_Future {
	return AuthResponse_Future{Future: p.Future.Field(0, nil)}
}

type RegisterRequest struct{ capnp.Struct }

// RegisterRequest_TypeID is the unique identifier for the type RegisterRequest.
const RegisterRequest_TypeID = 0x8a21a43d866e69f4

func NewRegisterRequest(s *capnp.Segment) (RegisterRequest, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 8, PointerCount: 6})
	return RegisterRequest{st}, err
}

func NewRootRegisterRequest(s *capnp.Segment) (RegisterRequest, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 8, PointerCount: 6})
	return RegisterRequest{st}, err
}

func ReadRootRegisterRequest(msg *capnp.Message) (RegisterRequest, error) {
	root, err := msg.Root()
	return RegisterRequest{root.Struct()}, err
}

func (s RegisterRequest) String() string {
	str, _ := text.Marshal(0x8a21a43d866e69f4, s.Struct)
	return str
}

func (s RegisterRequest) SystemId() (string, error) {
	p, err := s.Struct.Ptr(0)
	return p.Text(), err
}

func (s RegisterRequest) HasSystemId() bool {
	return s.Struct.HasPtr(0)
}

func (s RegisterRequest) SystemIdBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(0)
	return p.TextBytes(), err
}

func (s RegisterRequest) SetSystemId(v string) error {
	return s.Struct.SetText(0, v)
}

func (s RegisterRequest) Hostname() (string, error) {
	p, err := s.Struct.Ptr(1)
	return p.Text(), err
}

func (s RegisterRequest) HasHostname() bool {
	return s.Struct.HasPtr(1)
}

func (s RegisterRequest) HostnameBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(1)
	return p.TextBytes(), err
}

func (s RegisterRequest) SetHostname(v string) error {
	return s.Struct.SetText(1, v)
}

func (s RegisterRequest) Interfaces() (Interfaces, error) {
	p, err := s.Struct.Ptr(2)
	return Interfaces{Struct: p.Struct()}, err
}

func (s RegisterRequest) HasInterfaces() bool {
	return s.Struct.HasPtr(2)
}

func (s RegisterRequest) SetInterfaces(v Interfaces) error {
	return s.Struct.SetPtr(2, v.Struct.ToPtr())
}

// NewInterfaces sets the interfaces field to a newly
// allocated Interfaces struct, preferring placement in s's segment.
func (s RegisterRequest) NewInterfaces() (Interfaces, error) {
	ss, err := NewInterfaces(s.Struct.Segment())
	if err != nil {
		return Interfaces{}, err
	}
	err = s.Struct.SetPtr(2, ss.Struct.ToPtr())
	return ss, err
}

func (s RegisterRequest) Url() (string, error) {
	p, err := s.Struct.Ptr(3)
	return p.Text(), err
}

func (s RegisterRequest) HasUrl() bool {
	return s.Struct.HasPtr(3)
}

func (s RegisterRequest) UrlBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(3)
	return p.TextBytes(), err
}

func (s RegisterRequest) SetUrl(v string) error {
	return s.Struct.SetText(3, v)
}

func (s RegisterRequest) Nodegroup() (string, error) {
	p, err := s.Struct.Ptr(4)
	return p.Text(), err
}

func (s RegisterRequest) HasNodegroup() bool {
	return s.Struct.HasPtr(4)
}

func (s RegisterRequest) NodegroupBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(4)
	return p.TextBytes(), err
}

func (s RegisterRequest) SetNodegroup(v string) error {
	return s.Struct.SetText(4, v)
}

func (s RegisterRequest) BeaconSupport() bool {
	return s.Struct.Bit(0)
}

func (s RegisterRequest) SetBeaconSupport(v bool) {
	s.Struct.SetBit(0, v)
}

func (s RegisterRequest) Version() (string, error) {
	p, err := s.Struct.Ptr(5)
	return p.Text(), err
}

func (s RegisterRequest) HasVersion() bool {
	return s.Struct.HasPtr(5)
}

func (s RegisterRequest) VersionBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(5)
	return p.TextBytes(), err
}

func (s RegisterRequest) SetVersion(v string) error {
	return s.Struct.SetText(5, v)
}

// RegisterRequest_List is a list of RegisterRequest.
type RegisterRequest_List struct{ capnp.List }

// NewRegisterRequest creates a new list of RegisterRequest.
func NewRegisterRequest_List(s *capnp.Segment, sz int32) (RegisterRequest_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 8, PointerCount: 6}, sz)
	return RegisterRequest_List{l}, err
}

func (s RegisterRequest_List) At(i int) RegisterRequest { return RegisterRequest{s.List.Struct(i)} }

func (s RegisterRequest_List) Set(i int, v RegisterRequest) error {
	return s.List.SetStruct(i, v.Struct)
}

func (s RegisterRequest_List) String() string {
	str, _ := text.MarshalList(0x8a21a43d866e69f4, s.List)
	return str
}

// RegisterRequest_Future is a wrapper for a RegisterRequest promised by a client call.
type RegisterRequest_Future struct{ *capnp.Future }

func (p RegisterRequest_Future) Struct() (RegisterRequest, error) {
	s, err := p.Future.Struct()
	return RegisterRequest{s}, err
}

func (p RegisterRequest_Future) Interfaces() Interfaces_Future {
	return Interfaces_Future{Future: p.Future.Field(2, nil)}
}

type RegisterResponse struct{ capnp.Struct }

// RegisterResponse_TypeID is the unique identifier for the type RegisterResponse.
const RegisterResponse_TypeID = 0x971fe28893233a11

func NewRegisterResponse(s *capnp.Segment) (RegisterResponse, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 3})
	return RegisterResponse{st}, err
}

func NewRootRegisterResponse(s *capnp.Segment) (RegisterResponse, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 3})
	return RegisterResponse{st}, err
}

func ReadRootRegisterResponse(msg *capnp.Message) (RegisterResponse, error) {
	root, err := msg.Root()
	return RegisterResponse{root.Struct()}, err
}

func (s RegisterResponse) String() string {
	str, _ := text.Marshal(0x971fe28893233a11, s.Struct)
	return str
}

func (s RegisterResponse) SystemId() (string, error) {
	p, err := s.Struct.Ptr(0)
	return p.Text(), err
}

func (s RegisterResponse) HasSystemId() bool {
	return s.Struct.HasPtr(0)
}

func (s RegisterResponse) SystemIdBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(0)
	return p.TextBytes(), err
}

func (s RegisterResponse) SetSystemId(v string) error {
	return s.Struct.SetText(0, v)
}

func (s RegisterResponse) Uuid() (string, error) {
	p, err := s.Struct.Ptr(1)
	return p.Text(), err
}

func (s RegisterResponse) HasUuid() bool {
	return s.Struct.HasPtr(1)
}

func (s RegisterResponse) UuidBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(1)
	return p.TextBytes(), err
}

func (s RegisterResponse) SetUuid(v string) error {
	return s.Struct.SetText(1, v)
}

func (s RegisterResponse) Version() (string, error) {
	p, err := s.Struct.Ptr(2)
	return p.Text(), err
}

func (s RegisterResponse) HasVersion() bool {
	return s.Struct.HasPtr(2)
}

func (s RegisterResponse) VersionBytes() ([]byte, error) {
	p, err := s.Struct.Ptr(2)
	return p.TextBytes(), err
}

func (s RegisterResponse) SetVersion(v string) error {
	return s.Struct.SetText(2, v)
}

// RegisterResponse_List is a list of RegisterResponse.
type RegisterResponse_List struct{ capnp.List }

// NewRegisterResponse creates a new list of RegisterResponse.
func NewRegisterResponse_List(s *capnp.Segment, sz int32) (RegisterResponse_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 0, PointerCount: 3}, sz)
	return RegisterResponse_List{l}, err
}

func (s RegisterResponse_List) At(i int) RegisterResponse { return RegisterResponse{s.List.Struct(i)} }

func (s RegisterResponse_List) Set(i int, v RegisterResponse) error {
	return s.List.SetStruct(i, v.Struct)
}

func (s RegisterResponse_List) String() string {
	str, _ := text.MarshalList(0x971fe28893233a11, s.List)
	return str
}

// RegisterResponse_Future is a wrapper for a RegisterResponse promised by a client call.
type RegisterResponse_Future struct{ *capnp.Future }

func (p RegisterResponse_Future) Struct() (RegisterResponse, error) {
	s, err := p.Future.Struct()
	return RegisterResponse{s}, err
}

type Registerer struct{ Client *capnp.Client }

// Registerer_TypeID is the unique identifier for the type Registerer.
const Registerer_TypeID = 0xe75723043cae2d20

func (c Registerer) Register(ctx context.Context, params func(Registerer_register_Params) error) (Registerer_register_Results_Future, capnp.ReleaseFunc) {
	s := capnp.Send{
		Method: capnp.Method{
			InterfaceID:   0xe75723043cae2d20,
			MethodID:      0,
			InterfaceName: "handshake.capnp:Registerer",
			MethodName:    "register",
		},
	}
	if params != nil {
		s.ArgsSize = capnp.ObjectSize{DataSize: 0, PointerCount: 1}
		s.PlaceArgs = func(s capnp.Struct) error { return params(Registerer_register_Params{Struct: s}) }
	}
	ans, release := c.Client.SendCall(ctx, s)
	return Registerer_register_Results_Future{Future: ans.Future()}, release
}

func (c Registerer) AddRef() Registerer {
	return Registerer{
		Client: c.Client.AddRef(),
	}
}

func (c Registerer) Release() {
	c.Client.Release()
}

// A Registerer_Server is a Registerer with a local implementation.
type Registerer_Server interface {
	Register(context.Context, Registerer_register) error
}

// Registerer_NewServer creates a new Server from an implementation of Registerer_Server.
func Registerer_NewServer(s Registerer_Server, policy *server.Policy) *server.Server {
	c, _ := s.(server.Shutdowner)
	return server.New(Registerer_Methods(nil, s), s, c, policy)
}

// Registerer_ServerToClient creates a new Client from an implementation of Registerer_Server.
// The caller is responsible for calling Release on the returned Client.
func Registerer_ServerToClient(s Registerer_Server, policy *server.Policy) Registerer {
	return Registerer{Client: capnp.NewClient(Registerer_NewServer(s, policy))}
}

// Registerer_Methods appends Methods to a slice that invoke the methods on s.
// This can be used to create a more complicated Server.
func Registerer_Methods(methods []server.Method, s Registerer_Server) []server.Method {
	if cap(methods) == 0 {
		methods = make([]server.Method, 0, 1)
	}

	methods = append(methods, server.Method{
		Method: capnp.Method{
			InterfaceID:   0xe75723043cae2d20,
			MethodID:      0,
			InterfaceName: "handshake.capnp:Registerer",
			MethodName:    "register",
		},
		Impl: func(ctx context.Context, call *server.Call) error {
			return s.Register(ctx, Registerer_register{call})
		},
	})

	return methods
}

// Registerer_register holds the state for a server call to Registerer.register.
// See server.Call for documentation.
type Registerer_register struct {
	*server.Call
}

// Args returns the call's arguments.
func (c Registerer_register) Args() Registerer_register_Params {
	return Registerer_register_Params{Struct: c.Call.Args()}
}

// AllocResults allocates the results struct.
func (c Registerer_register) AllocResults() (Registerer_register_Results, error) {
	r, err := c.Call.AllocResults(capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Registerer_register_Results{Struct: r}, err
}

type Registerer_register_Params struct{ capnp.Struct }

// Registerer_register_Params_TypeID is the unique identifier for the type Registerer_register_Params.
const Registerer_register_Params_TypeID = 0x80a0e6cbaa396ef4

func NewRegisterer_register_Params(s *capnp.Segment) (Registerer_register_Params, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Registerer_register_Params{st}, err
}

func NewRootRegisterer_register_Params(s *capnp.Segment) (Registerer_register_Params, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Registerer_register_Params{st}, err
}

func ReadRootRegisterer_register_Params(msg *capnp.Message) (Registerer_register_Params, error) {
	root, err := msg.Root()
	return Registerer_register_Params{root.Struct()}, err
}

func (s Registerer_register_Params) String() string {
	str, _ := text.Marshal(0x80a0e6cbaa396ef4, s.Struct)
	return str
}

func (s Registerer_register_Params) Req() (RegisterRequest, error) {
	p, err := s.Struct.Ptr(0)
	return RegisterRequest{Struct: p.Struct()}, err
}

func (s Registerer_register_Params) HasReq() bool {
	return s.Struct.HasPtr(0)
}

func (s Registerer_register_Params) SetReq(v RegisterRequest) error {
	return s.Struct.SetPtr(0, v.Struct.ToPtr())
}

// NewReq sets the req field to a newly
// allocated RegisterRequest struct, preferring placement in s's segment.
func (s Registerer_register_Params) NewReq() (RegisterRequest, error) {
	ss, err := NewRegisterRequest(s.Struct.Segment())
	if err != nil {
		return RegisterRequest{}, err
	}
	err = s.Struct.SetPtr(0, ss.Struct.ToPtr())
	return ss, err
}

// Registerer_register_Params_List is a list of Registerer_register_Params.
type Registerer_register_Params_List struct{ capnp.List }

// NewRegisterer_register_Params creates a new list of Registerer_register_Params.
func NewRegisterer_register_Params_List(s *capnp.Segment, sz int32) (Registerer_register_Params_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1}, sz)
	return Registerer_register_Params_List{l}, err
}

func (s Registerer_register_Params_List) At(i int) Registerer_register_Params {
	return Registerer_register_Params{s.List.Struct(i)}
}

func (s Registerer_register_Params_List) Set(i int, v Registerer_register_Params) error {
	return s.List.SetStruct(i, v.Struct)
}

func (s Registerer_register_Params_List) String() string {
	str, _ := text.MarshalList(0x80a0e6cbaa396ef4, s.List)
	return str
}

// Registerer_register_Params_Future is a wrapper for a Registerer_register_Params promised by a client call.
type Registerer_register_Params_Future struct{ *capnp.Future }

func (p Registerer_register_Params_Future) Struct() (Registerer_register_Params, error) {
	s, err := p.Future.Struct()
	return Registerer_register_Params{s}, err
}

func (p Registerer_register_Params_Future) Req() RegisterRequest_Future {
	return RegisterRequest_Future{Future: p.Future.Field(0, nil)}
}

type Registerer_register_Results struct{ capnp.Struct }

// Registerer_register_Results_TypeID is the unique identifier for the type Registerer_register_Results.
const Registerer_register_Results_TypeID = 0xb5c83b347e16691c

func NewRegisterer_register_Results(s *capnp.Segment) (Registerer_register_Results, error) {
	st, err := capnp.NewStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Registerer_register_Results{st}, err
}

func NewRootRegisterer_register_Results(s *capnp.Segment) (Registerer_register_Results, error) {
	st, err := capnp.NewRootStruct(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1})
	return Registerer_register_Results{st}, err
}

func ReadRootRegisterer_register_Results(msg *capnp.Message) (Registerer_register_Results, error) {
	root, err := msg.Root()
	return Registerer_register_Results{root.Struct()}, err
}

func (s Registerer_register_Results) String() string {
	str, _ := text.Marshal(0xb5c83b347e16691c, s.Struct)
	return str
}

func (s Registerer_register_Results) Resp() (RegisterResponse, error) {
	p, err := s.Struct.Ptr(0)
	return RegisterResponse{Struct: p.Struct()}, err
}

func (s Registerer_register_Results) HasResp() bool {
	return s.Struct.HasPtr(0)
}

func (s Registerer_register_Results) SetResp(v RegisterResponse) error {
	return s.Struct.SetPtr(0, v.Struct.ToPtr())
}

// NewResp sets the resp field to a newly
// allocated RegisterResponse struct, preferring placement in s's segment.
func (s Registerer_register_Results) NewResp() (RegisterResponse, error) {
	ss, err := NewRegisterResponse(s.Struct.Segment())
	if err != nil {
		return RegisterResponse{}, err
	}
	err = s.Struct.SetPtr(0, ss.Struct.ToPtr())
	return ss, err
}

// Registerer_register_Results_List is a list of Registerer_register_Results.
type Registerer_register_Results_List struct{ capnp.List }

// NewRegisterer_register_Results creates a new list of Registerer_register_Results.
func NewRegisterer_register_Results_List(s *capnp.Segment, sz int32) (Registerer_register_Results_List, error) {
	l, err := capnp.NewCompositeList(s, capnp.ObjectSize{DataSize: 0, PointerCount: 1}, sz)
	return Registerer_register_Results_List{l}, err
}

func (s Registerer_register_Results_List) At(i int) Registerer_register_Results {
	return Registerer_register_Results{s.List.Struct(i)}
}

func (s Registerer_register_Results_List) Set(i int, v Registerer_register_Results) error {
	return s.List.SetStruct(i, v.Struct)
}

func (s Registerer_register_Results_List) String() string {
	str, _ := text.MarshalList(0xb5c83b347e16691c, s.List)
	return str
}

// Registerer_register_Results_Future is a wrapper for a Registerer_register_Results promised by a client call.
type Registerer_register_Results_Future struct{ *capnp.Future }

func (p Registerer_register_Results_Future) Struct() (Registerer_register_Results, error) {
	s, err := p.Future.Struct()
	return Registerer_register_Results{s}, err
}

func (p Registerer_register_Results_Future) Resp() RegisterResponse_Future {
	return RegisterResponse_Future{Future: p.Future.Field(0, nil)}
}

const schema_dceab81b996ed67b = "x\xda\x8cTM\x88\x1cE\x18}\xaf\xaa\xbb'\x09\xbb" +
	"\xcc\x14=zI\xe2F\xb3\x07W\xd8%\x92\x04qU" +
	"6F%\xc9\xa2\xb8\xb51(\xb9uf\xca\xdd1;" +
	"=\x93\xae\x1e%\xc6\x9f\x10QTPQ\xc1?<\x08" +
	"\x8a\x82\x88z0\xa0\xa0\x12\xc1\xc0\x82\x04\x12\x10\x7f\xe2" +
	"^\xa2!J\xc0\x8b\xe4\xe2AZj\xdc\xe9\xe9L\x0c" +
	"\xd9[\xd7\xc7\xeb\xf7\xbd\xef\xbd\xaao\xd3Ub\x9b\xb8" +
	"\xd1\xbf)\x00\xf4N?\xc8^\xfc\xe6\xd0\xa3\x1f\xfc\xb6" +
	"\xe60TEf\x87~\x88\xdf\\\xfb\xf9\xf9%\x80!" +
	"\xe5_\xe1\xb0,\x01\xe1j\xb9#\xdc\xea\xbe\xb2\x0b\xf1" +
	"\xcd\x1f~w\xee\x9d\xc3Pk\x09\xf8,\x01\x9b\xd7\xcb" +
	"\xbd\x04\xc319\x05f\x17\x1a\xf13\xb7\xbdw\xed\xf3" +
	"\xd0\x15\xb2O\xe7\x07\x0e\xb9K\x0a\x86{\x1c\xd1f-" +
	"_\"\x98m?\xf8\xdcS\xe7\x1e;\xf6\x1a\xd459" +
	"\xdf\x9f\xde[\x8e\xef\x1f\xcf\xf1\xa9\xc9\x8d\xaf>\xfb\xeb" +
	"\xc8\xebP\x95\"]\x97c\xbd\xbf\x86\xe1\xb8\xef\x14\x8e" +
	"\xf9\x9f\x80\xd9\x99\xb3\x1b~<2\xf5\xe9\x1b\x03`\xe1" +
	"\x10\xc7\xfd\xf3\xe1\xa9.\xf6\x84\xff\x08\x98\xadk\\\xfd" +
	"\xc4\x96[\x16\x8f\x16'\x19\x0b\xf6\xb9\xce[\x03\xd7y" +
	"\xf7\xfb\xd9\xe9\xaf\xdf\xfd\xe8\x97\xa2\xb4=\xc1+\x0e`" +
	"\xba\x80\x0d\xe3\x1f\xdf\xeam\xbc\xff\xf7K\x8c{:8" +
	"\x1d\xbe\xec\x06\x0e_\x08v\x84_\x04%\xd4\xb2\xf9(" +
	"\xae\xdb\xf9h\xbf0\x13\xb5\xa8\x1d\xb7'o\xef\xa4\xf3" +
	"&N\x1b#\xb5(m%3\xa4\xf6\xa4\x0f\xe4m\xd9" +
	"\xb3F\xa9\x87 \xd4\xeaR\x16-\xff\x81r-J\xcd" +
	"6\xce\x909\xad\xd7\xa3\x9d5s\x0d\x9b\x9a\xc4$\x13" +
	"\xc9\xf2\xe7\xe8L\x94D\xb2i\xb5'=\xc0#\xa0\x86" +
	"\xaf\x03\xf4*I]\x15,%\xe6\x00+\xfd\xe0@V" +
	"\xd0g\x96\x83\xcc\xb3\xe6@\xc7\xd8\x14N\xf2\xba\x9c\xf1" +
	"\xe84\xa0?\x93\xd4\xc7\x04\x15Y\xa5+~\xe5\x8a_" +
	"J\xeaEA%D\x95\x02P\xc7\xf7\x02\xfa[I}" +
	"RPIY\xa5\x04\xd4\x09'hQR\x7f/\xa8<" +
	"\xafJ\x0fP\xa7f\x01}RR/\x09\xd2\xaf\xd2\x07" +
	"\xd4\xcf\x09\xa0\x7f\x92\xd4g\x05U\xe0W\x19\x00\xea\xcc" +
	"v@/I\xea?\x043{\xd0\xa6\xa6\xb9\xab\x0e\x80" +
	"C\x10\x1cr\xc3\xb4l\x1aGMS\xac5\xe2\xd4$" +
	"\x0fF5HcY\xc9\xee\x98~\xfc\xef{\xdf\xde\x7f" +
	"dy\xfeR'Y\xc8\xa1q\xabn\xe6\x92V\x07l" +
	"\xe7\xb5}&\xaa\xb5\xe2\xdd\x1d\x8c\xb4\xdb\xad$%!" +
	"H\xf0\xc9\x87Mb\x1b\xad\xb8\xdfz\xd9G\x7f0\xf8" +
	"n\xee\x13Q\xffdFg\x8d\xed,\xc8\xf4\xa2\xa4n" +
	"\xe8'UN\x8cm\xb3\xd2\xbf\xe6W\x8e\xca\xb6[\xb1" +
	"5\xe8\x865\x94\x93\xde\xe5r\xb9SR\xcf\x14\xc2\xba" +
	"\xc7u\xda)\xa9\xef+\x84\xa5\x9d\xb3wK\xea\x07\xfe" +
	"\xdf\xd9r\xa7\xd3\xa8\xf7\x0e\x97\x9d\xfd\xa2K\xefD\x95" +
	"\x9d*\xa7iU\xaei\xcc\xb5\x1f\x95\xd4\x9b\x0a\x9a\xc6" +
	"'\x01}\xbd\xa4\xde\"X\xb6\xd1B\xcaa\x08\x0e\x83" +
	"S\xf5\xc6\x9c\xb1\xf9qe\xef\xc0\xd9[Z\xb8\xa2\xbd" +
	"\xf9\xca\x19\xb0w%\x09\xba\xa7\xd6\xe4e\x9fZ\xd3\xce" +
	"]\"Y\x0cJ\x96\xa6\xb0\x0ez\x0b\x97\xbd}\xa5\xd4" +
	"\xf4\x7f\xeb\xa07\x16\x80\xee.\xf87\x00\x00\xff\xff\x86" +
	"\xdc\x84m"

func init() {
	schemas.Register(schema_dceab81b996ed67b,
		0x800ae3a77a7bc18e,
		0x80a0e6cbaa396ef4,
		0x8a21a43d866e69f4,
		0x96c07ce683897942,
		0x971fe28893233a11,
		0x98b03f82d720e4e1,
		0xb5c83b347e16691c,
		0xdbaca3bedaffa653,
		0xe75723043cae2d20)
}
