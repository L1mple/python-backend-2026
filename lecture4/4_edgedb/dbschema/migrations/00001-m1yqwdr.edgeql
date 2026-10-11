CREATE MIGRATION m1yqwdrhoqjdsgwpb6r5albr7ak7tpwivccs2vm4uvuegcs6di4kkq
    ONTO initial
{
  CREATE TYPE default::Order {
      CREATE PROPERTY created_at: std::datetime {
          SET default := (std::datetime_current());
      };
      CREATE REQUIRED PROPERTY quantity: std::int32 {
          CREATE CONSTRAINT std::min_value(1);
      };
      CREATE PROPERTY status: std::str {
          SET default := 'pending';
          CREATE CONSTRAINT std::one_of('pending', 'processing', 'shipped', 'delivered', 'cancelled');
      };
      CREATE REQUIRED PROPERTY total_price: std::decimal {
          CREATE CONSTRAINT std::min_value(0);
      };
  };
  CREATE TYPE default::Product {
      CREATE PROPERTY created_at: std::datetime {
          SET default := (std::datetime_current());
      };
      CREATE PROPERTY description: std::str;
      CREATE PROPERTY in_stock: std::bool {
          SET default := true;
      };
      CREATE REQUIRED PROPERTY name: std::str;
      CREATE REQUIRED PROPERTY price: std::decimal {
          CREATE CONSTRAINT std::min_value(0);
      };
  };
  ALTER TYPE default::Order {
      CREATE REQUIRED LINK product: default::Product;
  };
  ALTER TYPE default::Product {
      CREATE MULTI LINK orders := (.<product[IS default::Order]);
  };
  CREATE TYPE default::User {
      CREATE REQUIRED PROPERTY age: std::int32 {
          CREATE CONSTRAINT std::min_value(0);
      };
      CREATE PROPERTY created_at: std::datetime {
          SET default := (std::datetime_current());
      };
      CREATE REQUIRED PROPERTY email: std::str {
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY name: std::str;
  };
  ALTER TYPE default::Order {
      CREATE REQUIRED LINK user: default::User;
  };
  ALTER TYPE default::User {
      CREATE MULTI LINK orders := (.<user[IS default::Order]);
  };
};
