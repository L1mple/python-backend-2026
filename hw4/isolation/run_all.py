from isolation import dirty_read, non_repeatable_read, phantom_read, serialization

if __name__ == "__main__":
    dirty_read.main()
    non_repeatable_read.main()
    phantom_read.main()
    serialization.main()
