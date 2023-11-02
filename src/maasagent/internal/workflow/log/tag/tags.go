package tag

type builder struct {
	KeyVals []interface{}
}

func Builder() *builder {
	return &builder{}
}

// TargetSystemID provides KV with a tag for the given systemID
func (b *builder) TargetSystemID(systemID string) *builder {
	return b.KV("target_system_id", systemID)
}

// Error provides a KV with a tag for the given error
func (b *builder) Error(err error) *builder {
	return b.KV("error", err)
}

func (b *builder) KV(key, value interface{}) *builder {
	b.KeyVals = append(b.KeyVals, key, value)
	return b
}
