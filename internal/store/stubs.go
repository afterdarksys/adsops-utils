package store

import "database/sql"

// GroupStore handles group database operations
type GroupStore struct {
	db *sql.DB
}

// ContactStore handles contact database operations
type ContactStore struct {
	db *sql.DB
}

// EmployeeStore handles employee profile database operations
type EmployeeStore struct {
	db *sql.DB
}

// ACLStore handles ticket ACL database operations
type ACLStore struct {
	db *sql.DB
}
