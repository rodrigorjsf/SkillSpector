package com.example;

import java.util.List;

/**
 * Reads customer orders. Nothing about agents, Skills or tools.
 *
 * <p>Here so the fixture is a negative control as well as a positive one: an ordinary
 * class in a LangChain4j application is opened by the Analyzer and yields nothing, and
 * the snapshot pins that silence.
 */
public class OrderRepository {

    public List<String> openOrders(String customerId) {
        return List.of();
    }

    public String orderTier(String orderId) {
        return "standard";
    }
}
