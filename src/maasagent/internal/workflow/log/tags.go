package log

// SystemIDTag is a Temporal logger tag for target
// system_id's
type SystemIDTag struct {
	systemID string
}

// NewSystemIDTag provides a tag for the given system_id
func NewSystemIDTag(systemID string) SystemIDTag {
	return SystemIDTag{
		systemID: systemID,
	}
}

// Key implements the temporal tag.Tag interface's Key() method
func (s SystemIDTag) Key() string {
	return "target_system_id"
}

// Value implements the temporal tag.Tag interface's Value() method
func (s SystemIDTag) Value() interface{} {
	return s.systemID
}
