package netmon

import (
	"encoding/json"
	"errors"
	"fmt"
)

// Event is an enum value for the type of event observed
type Event uint8

const (
	// EventNew is the Event value for a new Result
	EventNew Event = iota + 1
	// EventRefreshed is the Event value for a Result that is for
	// refreshed ARP values
	EventRefreshed
	// EventMoved is the Event value for a Result where the IP has
	// changed its MAC address
	EventMoved
)

const (
	eventNewStr       = "NEW"
	eventRefreshedStr = "REFRESHED"
	eventMovedStr     = "MOVED"
)

var (
	eventToString = map[Event]string{
		EventNew:       eventNewStr,
		EventRefreshed: eventRefreshedStr,
		EventMoved:     eventMovedStr,
	}

	stringToEvent = map[string]Event{
		eventNewStr:       EventNew,
		eventRefreshedStr: EventRefreshed,
		eventMovedStr:     EventMoved,
	}
)

var (
	errInvalidEvent = errors.New("invalid event")
)

// String returns the string version of the Event
func (e Event) String() string {
	str, ok := eventToString[e]
	if ok {
		return str
	}

	return "UNKNOWN"
}

// ValidString returns the string version of the Event and errors if
// a non-valid one was given
func (e Event) ValidString() (string, error) {
	str, ok := eventToString[e]
	if !ok {
		return "", fmt.Errorf("%w: %d", errInvalidEvent, e)
	}

	return str, nil
}

// MarshalJSON implements json.Marshaler for Event
func (e Event) MarshalJSON() ([]byte, error) {
	eventStr, err := e.ValidString()
	if err != nil {
		return nil, err
	}

	b, err := json.Marshal(eventStr)
	if err != nil {
		return nil, err
	}

	return b, nil
}

// UnmarshalJSON implements the json.Unmarshaler for Event
func (e *Event) UnmarshalJSON(b []byte) error {
	var eventStr string

	err := json.Unmarshal(b, &eventStr)
	if err != nil {
		return err
	}

	var ok bool

	*e, ok = stringToEvent[eventStr]
	if !ok {
		return fmt.Errorf("%w string: %s", errInvalidEvent, eventStr)
	}

	return nil
}
