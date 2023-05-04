package netmon

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
)

type eventStringCase struct {
	Name string
	Out  string
	In   Event
}

func TestEventString(t *testing.T) {
	table := []eventStringCase{
		{
			Name: "EventNew",
			In:   EventNew,
			Out:  eventNewStr,
		},
		{
			Name: "EventRefreshed",
			In:   EventRefreshed,
			Out:  eventRefreshedStr,
		},
		{
			Name: "EventMoved",
			In:   EventMoved,
			Out:  eventMovedStr,
		},
		{
			Name: "Unknown",
			In:   Event(0xff),
			Out:  "UNKNOWN",
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			assert.Equalf(tt, tcase.Out, tcase.In.String(), "expected a string of %s", tcase.Out)
		})
	}
}

type eventValidStringCase struct {
	Err error
	eventStringCase
}

func TestEventValidString(t *testing.T) {
	table := []eventValidStringCase{
		{
			eventStringCase: eventStringCase{
				Name: "EventNew",
				In:   EventNew,
				Out:  eventNewStr,
			},
		},
		{
			eventStringCase: eventStringCase{
				Name: "EventRefreshed",
				In:   EventRefreshed,
				Out:  eventRefreshedStr,
			},
		},
		{
			eventStringCase: eventStringCase{
				Name: "EventMoved",
				In:   EventMoved,
				Out:  eventMovedStr,
			},
		},
		{
			eventStringCase: eventStringCase{
				Name: "Unknown",
				In:   Event(0xff),
			},
			Err: errInvalidEvent,
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			str, err := tcase.In.ValidString()
			assert.Equalf(tt, tcase.Out, str, "expected a string of %s", tcase.Out)
			assert.ErrorIs(tt, err, tcase.Err)
		})
	}
}

type eventMarshalJSONCase struct {
	Err  error
	Name string
	Out  []byte
	In   Event
}

func TestMarshalJSON(t *testing.T) {
	table := []eventMarshalJSONCase{
		{
			Name: "EventNew",
			In:   EventNew,
			Out:  []byte("\"" + eventNewStr + "\""),
		},
		{
			Name: "EventRefreshed",
			In:   EventRefreshed,
			Out:  []byte("\"" + eventRefreshedStr + "\""),
		},
		{
			Name: "EventMoved",
			In:   EventMoved,
			Out:  []byte("\"" + eventMovedStr + "\""),
		},
		{
			Name: "Uknown",
			In:   Event(0xff),
			Err:  errInvalidEvent,
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			b, err := tcase.In.MarshalJSON()
			assert.Equalf(tt, b, tcase.Out, "expected event to marshal to %s", tcase.Out)
			assert.ErrorIs(tt, err, tcase.Err)
		})
	}
}

type eventUnmarshalJSONCase struct {
	Name string
	Err  error
	In   []byte
	Out  Event
}

func TestEventUnmarshalJSON(t *testing.T) {
	table := []eventUnmarshalJSONCase{
		{
			Name: "EventNew",
			In:   []byte("\"NEW\""),
			Out:  EventNew,
		},
		{
			Name: "EventRefreshed",
			In:   []byte("\"REFRESHED\""),
			Out:  EventRefreshed,
		},
		{
			Name: "EventMoved",
			In:   []byte("\"MOVED\""),
			Out:  EventMoved,
		},
		{
			Name: "Empty",
			Err:  &json.SyntaxError{},
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			var e Event
			err := e.UnmarshalJSON(tcase.In)
			assert.Equalf(tt, tcase.Out, e, "expected event to equal %s", tcase.Out)
			if tcase.Err != nil {
				assert.ErrorAs(tt, err, &tcase.Err)
			}
		})
	}
}
