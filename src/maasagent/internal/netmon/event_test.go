package netmon

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestEventString(t *testing.T) {
	t.Parallel()

	testcases := map[string]struct {
		in  Event
		out string
		err error
	}{
		"event new": {
			in:  EventNew,
			out: eventNewStr,
		},
		"event refreshed": {
			in:  EventRefreshed,
			out: eventRefreshedStr,
		},
		"event moved": {
			in:  EventMoved,
			out: eventMovedStr,
		},
		"unknown": {
			in:  Event(0xff),
			out: "UNKNOWN",
			err: errInvalidEvent,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()
			assert.Equal(t, tc.out, tc.in.String())
			_, err := tc.in.ValidString()
			if err != nil {
				assert.ErrorIs(t, err, tc.err)
			}
		})
	}
}

func TestMarshalJSON(t *testing.T) {
	t.Parallel()

	testcases := map[string]struct {
		in  Event
		out []byte
		err error
	}{
		"event new": {
			in:  EventNew,
			out: []byte("\"" + eventNewStr + "\""),
		},
		"event refreshed": {
			in:  EventRefreshed,
			out: []byte("\"" + eventRefreshedStr + "\""),
		},
		"event moved": {
			in:  EventMoved,
			out: []byte("\"" + eventMovedStr + "\""),
		},
		"unknown": {
			in:  Event(0xff),
			err: errInvalidEvent,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()
			b, err := tc.in.MarshalJSON()
			assert.Equal(t, tc.out, b)
			assert.ErrorIs(t, err, tc.err)
		})
	}
}

func TestEventUnmarshalJSON(t *testing.T) {
	t.Parallel()

	testcases := map[string]struct {
		in  []byte
		out Event
		err error
	}{
		"event new": {
			in:  []byte("\"NEW\""),
			out: EventNew,
		},
		"event refreshed": {
			in:  []byte("\"REFRESHED\""),
			out: EventRefreshed,
		},
		"event moved": {
			in:  []byte("\"MOVED\""),
			out: EventMoved,
		},
		"unknown": {
			err: &json.SyntaxError{},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()
			var e Event
			err := e.UnmarshalJSON(tc.in)
			if err == nil {
				assert.Equal(t, tc.out, e)
			} else {
				assert.IsType(t, tc.err, err)
			}
		})
	}
}
